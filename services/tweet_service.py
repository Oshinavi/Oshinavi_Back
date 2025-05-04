import logging
from datetime import datetime, timedelta
import re

from repository.tweet_repository import TweetRepository
from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from services.openai_translator import translate_japanese_tweet
from services.openai_reply_creator import reply_generator
from services.exceptions import NotFoundError, BadRequestError, ApiError
from models import Post, ReplyLog

logger = logging.getLogger(__name__)

# 트위터 트랜잭션 로직 관리
class TweetService:
    def __init__(self):
        self.repo = TweetRepository()
        self.twitter_client = TwitterClientService()
        self.twitter_user = TwitterUserService(self.twitter_client)

    ## 최신 트윗을 가져와 db에 저장 및 반환
    async def fetch_and_store_latest_tweets(self, screen_name: str) -> list[dict]:

        ## 트위터 유저 정보 취득
        await self.twitter_client.ensure_login()
        user_info = await self.twitter_user.get_user_info(screen_name)

        if not user_info:
            raise NotFoundError(f"User {screen_name} not found")

        author_internal_id = str(user_info['id'])
        profile_image_url = user_info['profile_image_url']

        ## 트위터 게시글 스크래핑
        client = self.twitter_client.get_client()
        tweets = await client.get_user_tweets(
            user_id=author_internal_id,
            tweet_type='Tweets',
            count=10
        )
        logger.debug(f"{len(tweets)} tweets fetched for {screen_name}")

        existing = self.repo.list_tweet_ids()
        new_posts = []

        ## 이미 db에 저장된 트윗 제외
        for t in tweets:
            if str(t.id) in existing:
                logger.debug(f"Duplicate tweet ignored: {t.id}")
                continue

            parsed = self._parse_twitter_datetime(t.created_at)
            if not parsed:
                logger.warning(f"Failed to parse date for tweet {t.id}")
                continue

            ## GPT API로 트윗 번역 및 포함일시 파싱
            translated = await translate_japanese_tweet(t.full_text, parsed)

            included_dt = None
            if translated["datetime"]:
                try:
                    included_dt = datetime.strptime(translated["datetime"], "%Y.%m.%d %H:%M:%S")
                except Exception as e:
                    raise ApiError(f"날짜 파싱 실패: {translated['datetime']}")

            ## db에 새 포스트 저장
            post = Post(
                tweet_id=t.id,
                author_internal_id=author_internal_id,
                tweet_date=parsed,
                tweet_included_date=included_dt,
                tweet_text=t.full_text,
                tweet_translated_text=translated["translated"],
                tweet_about=translated["category"]
            )
            self.repo.add_post(post)
            new_posts.append(post)

        # 트윗 반환
        try:
            if new_posts:
                self.repo.commit()
                logger.debug(f" {len(new_posts)}개의 새 트윗 저장 완료")
            posts = self.repo.list_by_username(screen_name)
            return [
                {
                    "tweet_id": str(p.tweet_id),
                    "tweet_userid": p.author.twitter_id,
                    "tweet_username": p.author.username,
                    "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "tweet_included_date": p.tweet_included_date.strftime(
                        "%Y-%m-%d %H:%M:%S") if p.tweet_included_date else None,
                    "tweet_text": p.tweet_text,
                    "tweet_translated_text": p.tweet_translated_text,
                    "tweet_about": p.tweet_about,
                    "profile_image_url": profile_image_url,
                }
                for p in posts
            ]
        except Exception as e:
            logger.error(f"DB 커밋 오류: {e}")
            self.repo.rollback()
            raise

    async def send_reply(self, tweet_id: str, tweet_text: str) -> dict:
        # 1) 로그인 보장
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        # 2) 원본 트윗 확인
        tweet = await client.get_tweet_by_id(tweet_id)
        if not tweet:
            raise NotFoundError("해당 트윗이 존재하지 않습니다.")

        # 3) 길이 제한
        length = self._calculate_tweet_length(tweet_text)
        if length > 280:
            raise BadRequestError("280자(글자 기준)를 초과할 수 없습니다.")

        # 4) 실제 전송 시도
        try:
            api_tweet = await client.create_tweet(text=tweet_text, reply_to=tweet_id)
        except Exception as e:
            msg = str(e)
            # 중복 리플라이 에러를 400으로 변환
            if "duplicate" in msg.lower() or "187" in msg:
                raise BadRequestError("이미 동일한 리플라이를 보냈습니다.")
            # 기타 예외는 500으로
            raise ApiError(f"리플라이 전송 중 오류: {msg}")

        # 5) JSON-serializable 형태로 변환
        tweet_info = {
            "reply_tweet_id": str(api_tweet.id),
            "created_at": api_tweet.created_at,
            "text": api_tweet.text,
        }

        # 6) DB에 로그 남기기
        log = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        try:
            self.repo.commit()
        except Exception as e:
            logger.error(f"리플라이 로그 커밋 실패: {e}")
            self.repo.rollback()

        # 7) 결과 반환
        return {
            "success": True,
            "message": "리플라이 전송 성공",
            "tweet_result": tweet_info
        }

    ## OpenAI API를 이용하여 답변 자동 생성
    async def generate_auto_reply(self, tweet_text: str) -> str:
        generated_reply = await reply_generator(tweet_text)

        # 생성된 리플라이가 비어있는 경우
        if not generated_reply:
            logger.error("응답이 비어 있습니다.")
            raise ApiError("리플라이 생성에 실패했습니다.")
        return generated_reply

    ## KST 시간에 맞게 datetime 형식 변환
    def _parse_twitter_datetime(self, dt_str: str) -> str | None:
        try:
            utc_dt_obj = datetime.strptime(dt_str, "%a %b %d %H:%M:%S %z %Y")
            kst_dt = utc_dt_obj + timedelta(hours=9)
            return kst_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f" 날짜 파싱 실패: {dt_str} → {e}")
            return None

    ## 글자수 제약 확인
    def _calculate_tweet_length(self, text: str) -> int:
        count = 0
        for char in text:
            # ASCII 문자 (영문, 숫자, 공백, 개행 등)
            if re.match(r'^[\x00-\x7F]$', char):
                count += 1
            else:
                count += 2
        return count
