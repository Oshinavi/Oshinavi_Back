from datetime import datetime, timedelta
import re

from services.openai_translator import translate_japanese_tweet
from services.openai_reply_creator import reply_generator
from repository.tweet_repository import TweetRepository
from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService

# 트위터 트랜잭션 로직 관리
class TweetService:
    def __init__(self):
        self.repo = TweetRepository()
        self.twitter_client = TwitterClientService()
        self.twitter_user = TwitterUserService(self.twitter_client)

    ## 최신 트윗을 가져와 db에 저장 및 반환
    async def fetch_and_store_latest_tweets(self, screen_name: str):

        ## 트위터 유저 정보 취득
        await self.twitter_client.ensure_login()
        user_info = await self.twitter_user.get_user_info(screen_name)

        if not user_info:
            raise ValueError(f"User {screen_name} not found")

        author_internal_id = str(user_info['id'])
        profile_image_url = user_info['profile_image_url']
        client = self.twitter_client.get_client()

        # user_id = str(user_info['id'])
        # username = user_info['username']
        # profile_image_url = user_info['profile_image_url']
        # client = self.twitter_client.get_client()

        ## 트위터 게시글 스크래핑
        tweets = await client.get_user_tweets(user_id=author_internal_id, tweet_type='Tweets', count=10)
        print(f" {len(tweets)}개의 트윗 수신됨")
        existing_ids = self.repo.get_existing_tweet_ids()
        new_posts = []

        ## 이미 db에 저장된 트윗 제외
        for tweet in tweets:
            if str(tweet.id) in existing_ids:
                print(f" 중복된 트윗 무시: {tweet.id}")
                continue

            parsed_date = self._parse_twitter_datetime(tweet.created_at)
            if not parsed_date:
                print(f" 트윗 {tweet.id} 날짜 파싱 실패로 저장 안 됨")
                continue

            ## GPT API로 트윗 번역 및 포함일시 파싱
            translated_data = await translate_japanese_tweet(tweet.full_text, parsed_date)

            included_dt = None
            if translated_data["datetime"]:
                try:
                    included_dt = datetime.strptime(translated_data["datetime"], "%Y.%m.%d %H:%M:%S")
                except Exception as e:
                    print(f"⚠ included_date 파싱 실패: {translated_data['datetime']} → {e}")

            ## db에 새 포스트 저장
            post = self.repo.save_post(
                tweet_id=tweet.id,
                author_internal_id=author_internal_id,
                tweet_date=parsed_date,
                tweet_included_date=included_dt,
                tweet_text=tweet.full_text,
                tweet_translated_text=translated_data["translated"],
                tweet_about=translated_data["category"],
            )
            new_posts.append(post)

        if new_posts:
            self.repo.save_all(new_posts)
            print(f" {len(new_posts)}개의 새 트윗 저장 완료")

        ## 지정된 개수 트윗 반환
        recent_posts = self.repo.get_recent_posts_by_username(
            username=screen_name,
            limit=20
        )

        return [
            {
                "tweet_id": str(p.tweet_id),
                "tweet_userid": p.author.twitter_id,
                "tweet_username": p.author.username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_included_date": p.tweet_included_date.strftime("%Y-%m-%d %H:%M:%S") if p.tweet_included_date else None,
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about": p.tweet_about,
                "profile_image_url": profile_image_url,
            }
            for p in recent_posts
        ]

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

    async def send_reply(self, tweet_id: str, tweet_text: str) -> dict:
        try:
            await self.twitter_client.ensure_login()
            client = self.twitter_client.get_client()

            # 트윗 유효성 체크(글이 삭제되었을 때 대비)
            tweet = await client.get_tweet_by_id(tweet_id)
            if not tweet:
                return {"success": False, "error": "해당 트윗이 존재하지 않습니다."}

            # 길이 제한 (280 byte 넘는지 확인)
            length = self._calculate_tweet_length(tweet_text)
            if length > 280:
                return {"success": False, "error": "트윗은 280자(글자 기준)를 초과할 수 없습니다."}

            # 리플라이 전송
            result = await client.create_tweet(text=tweet_text, reply_to=tweet_id)

            # 리플라이 로그를 DB에 저장
            self.repo.save_reply_log(tweet_id, tweet_text)

            # 예외 없이 성공 시
            return {"success": True, "message": "리플라이 전송 성공", "tweet_result": result}

        except ValueError as ve:
            print(f"입력 값 오류: {ve}")
            return {"success": False, "error": f"입력 오류: {ve}"}

        except TimeoutError:
            print("네트워크 타임아웃 발생")
            return {"success": False, "error": "네트워크 타임아웃이 발생했습니다."}

        except Exception as e:
            print(f"알 수 없는 오류 발생: {e}")
            return {"success": False, "error": f"예외 발생: {str(e)}"}

    ## OpenAI API를 이용하여 답변 자동 생성
    async def generate_auto_reply(self, tweet_text: str) -> str:
        try:
            generated_reply = await reply_generator(tweet_text)

            # 생성된 리플라이가 비어있는 경우
            if not generated_reply:
                print("응답이 비어 있습니다.")
                return "（리플라이 생성에 실패했습니다.）"

            return generated_reply

        except Exception as e:
            print(f"자동 리플라이 생성 오류: {e}")
            return "（리플라이 생성 중 에러가 발생했습니다.）"