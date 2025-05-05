import logging
import asyncio
from datetime import datetime, timedelta
import re
from sqlalchemy.exc import IntegrityError

from repository.tweet_repository import TweetRepository
from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from services.openai_translator import translate_japanese_tweet
from services.openai_reply_creator import reply_generator
from services.exceptions import NotFoundError, BadRequestError, ApiError
from models import Post, ReplyLog

logger = logging.getLogger(__name__)

class TweetService:
    def __init__(self):
        self.repo = TweetRepository()
        self.twitter_client = TwitterClientService()
        self.twitter_user = TwitterUserService(self.twitter_client)

    async def fetch_and_store_latest_tweets(self, screen_name: str) -> list[dict]:
        # 1) 로그인 및 사용자 정보
        await self.twitter_client.ensure_login()
        user_info = await self.twitter_user.get_user_info(screen_name)
        if not user_info:
            raise NotFoundError(f"User '{screen_name}' not found")
        author_internal_id = str(user_info['id'])
        profile_image_url  = user_info.get('profile_image_url')

        # 2) 최신 트윗 조회
        client = self.twitter_client.get_client()
        tweets = await client.get_user_tweets(
            user_id=author_internal_id,
            tweet_type='Tweets',
            count=10
        )

        # 이미 저장된 ID 목록
        existing_ids = set(self.repo.list_tweet_ids())
        new_posts = []

        for t in tweets:
            tid = str(t.id)
            if tid in existing_ids:
                continue  # 이미 저장됨

            # 3) 작성 시각 파싱 (UTC→KST)
            parsed_str = self._parse_twitter_datetime(t.created_at)
            if not parsed_str:
                logger.warning(f"날짜 파싱 실패: {t.created_at}")
                continue
            tweet_date = datetime.strptime(parsed_str, "%Y-%m-%d %H:%M:%S")

            # 4) GPT 번역 및 일정 추출
            try:
                translated = await translate_japanese_tweet(t.full_text, parsed_str)
            except Exception as e:
                logger.error(f"GPT 번역 실패: {e}")
                translated = {}

            # 번역문/카테고리 기본값 처리
            translated_text = translated.get("translated") or t.full_text
            category        = translated.get("category")   or "일반"

            # 시작/종료일자 파싱
            start_incl, end_incl = None, None
            if translated.get("start"):
                try:
                    start_incl = datetime.strptime(translated["start"], "%Y.%m.%d %H:%M:%S")
                except Exception as e:
                    logger.warning(f"시작일자 파싱 실패 ({translated['start']}): {e}")
            if translated.get("end"):
                try:
                    end_incl = datetime.strptime(translated["end"], "%Y.%m.%d %H:%M:%S")
                except Exception as e:
                    logger.warning(f"종료일자 파싱 실패 ({translated['end']}): {e}")

            # 5) DB에 저장
            post = Post(
                tweet_id                 = t.id,
                author_internal_id       = author_internal_id,
                tweet_date               = tweet_date,
                tweet_included_start_date= start_incl,
                tweet_included_end_date  = end_incl,
                tweet_text               = t.full_text,
                tweet_translated_text    = translated_text,
                tweet_about              = category
            )
            self.repo.add_post(post)
            new_posts.append(post)

        # 6) 커밋 (중복키는 무시)
        try:
            if new_posts:
                self.repo.commit()
        except IntegrityError as ie:
            logger.warning(f"중복 엔트리 발생, 스킵합니다: {ie}")
            self.repo.rollback()
        except Exception as e:
            logger.error(f"DB 커밋 오류: {e}")
            self.repo.rollback()
            raise

        # 7) 결과 반환
        posts = self.repo.list_by_username(screen_name)
        return [
            {
                "tweet_id": str(p.tweet_id),
                "tweet_userid": p.author.twitter_id,
                "tweet_username": p.author.username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_included_start_date": p.tweet_included_start_date.strftime("%Y-%m-%d %H:%M:%S") if p.tweet_included_start_date else None,
                "tweet_included_end_date":   p.tweet_included_end_date.strftime("%Y-%m-%d %H:%M:%S")   if p.tweet_included_end_date   else None,
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about": p.tweet_about,
                "profile_image_url": profile_image_url,
            }
            for p in posts
        ]

    async def send_reply(self, tweet_id: str, tweet_text: str) -> dict:
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        # 1) 존재 확인
        tweet = await client.get_tweet_by_id(tweet_id)
        if not tweet:
            raise NotFoundError("해당 트윗이 존재하지 않습니다.")

        # 2) 길이 제한
        if self._calculate_tweet_length(tweet_text) > 280:
            raise BadRequestError("280자(글자 기준)를 초과할 수 없습니다.")

        # 3) 전송 시도
        try:
            result = await client.create_tweet(text=tweet_text, reply_to=tweet_id)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "187" in msg:
                raise BadRequestError("이미 동일한 리플라이를 보냈습니다.")
            raise ApiError(f"리플라이 전송 중 오류: {e}")

        # 4) 로그 저장
        log = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        try:
            self.repo.commit()
        except Exception as e:
            logger.error(f"리플라이 로그 커밋 실패: {e}")
            self.repo.rollback()

        return {
            "success": True,
            "message": "리플라이 전송 성공",
            "tweet_result": {
                "reply_tweet_id": str(result.id),
                "created_at": result.created_at,
                "text": result.text,
            }
        }

    async def generate_auto_reply(self, tweet_text: str) -> str:
        try:
            gen = await reply_generator(tweet_text)
        except Exception as e:
            logger.error(f"자동 리플라이 생성 실패: {e}")
            raise ApiError("리플라이 생성에 실패했습니다.")
        if not gen:
            raise ApiError("리플라이 생성에 실패했습니다.")
        return gen

    def _parse_twitter_datetime(self, dt_str: str) -> str | None:
        try:
            utc_dt = datetime.strptime(dt_str, "%a %b %d %H:%M:%S %z %Y")
            kst_dt = utc_dt + timedelta(hours=9)
            return kst_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"날짜 파싱 오류: '{dt_str}' → {e}")
            return None

    def _calculate_tweet_length(self, text: str) -> int:
        count = 0
        for ch in text:
            count += 1 if re.match(r'^[\x00-\x7F]$', ch) else 2
        return count