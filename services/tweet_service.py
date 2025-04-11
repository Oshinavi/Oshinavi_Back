from datetime import datetime, timedelta

from services.openai_translator import translate_japanese_tweet
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

        user_id = str(user_info['id'])
        username = user_info['username']
        profileimageurl = user_info['profile_image_url']
        client = self.twitter_client.get_client()

        ## 트위터 게시글 스크래핑
        tweets = await client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=10)
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

            ## GPT API로 트윗 번역
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
                tweet_userid=str(user_id),
                tweet_username=username,
                tweet_date=parsed_date,
                tweet_included_date=included_dt,
                tweet_text=tweet.full_text,
                tweet_translated_text=translated_data["translated"],
                tweet_about=translated_data["category"]
            )
            new_posts.append(post)

        if new_posts:
            self.repo.save_all(new_posts)
            print(f" {len(new_posts)}개의 새 트윗 저장 완료")

        ## 지정된 개수 트윗 반환
        recent_posts = self.repo.get_recent_posts_by_username(username=username, limit=20)
        return [
            {
                "tweet_id": str(p.tweet_id),
                "tweet_userid": p.tweet_userid,
                "tweet_username": p.tweet_username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_included_date": p.tweet_included_date.strftime("%Y-%m-%d %H:%M:%S") if p.tweet_included_date else None,
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about": p.tweet_about,
                "profile_image_url": profileimageurl,
            } for p in recent_posts
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
