# import aiofiles
# import json
# import os
# import asyncio
# from datetime import datetime
# from twikit import Client
# from models import db, Post
# from Controller.openai_translator import translate_japanese_tweet  # 번역기 연동용
#
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# COOKIE_FILE = os.path.join(BASE_DIR, "..", "config", "twitter_cookies.json")
# client = Client('en-US')
#
# logged_in = False  # 로그인 상태 추적
#
# async def ensure_login():
#     global logged_in
#     if logged_in:
#         return
#     await load_cookies_and_login()
#     logged_in = True
#
# async def load_cookies_and_login():
#     """ 저장된 쿠키를 불러와 로그인 유지 """
#     if os.path.exists(COOKIE_FILE):
#         with open(COOKIE_FILE, "r") as f:
#             cookies = json.load(f)
#         # 쿠키를 클라이언트 세션에 적용
#         client.set_cookies(cookies)
#         print("✅ Login Successfully using cookies")
#     else:
#         raise FileNotFoundError("🚨 No cookie file found. Please log in again.")
#
# # async def load_cookies_and_login():
# #     file_exists = await asyncio.to_thread(os.path.exists, COOKIE_FILE)
# #     if not file_exists:
# #         raise FileNotFoundError("쿠키 파일이 없습니다.")
# #
# #     async with aiofiles.open(COOKIE_FILE, "r") as f:
# #         cookies = json.loads(await f.read())
# #     client.set_cookies(cookies)
#
# async def get_user_id(screen_name: str):
#     user = await client.get_user_by_screen_name(screen_name)
#     return user.id, user.name
#
# def parse_twitter_datetime(dt_str):
#     try:
#         return datetime.strptime(dt_str, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d %H:%M:%S")
#     except Exception as e:
#         print(f"❌ 날짜 파싱 실패: {dt_str} → {e}")
#         return None
#
# async def fetch_and_store_latest_tweets(screen_name: str):
#     # await load_cookies_and_login()
#     await ensure_login()
#     user_id, username = await get_user_id(screen_name)
#
#     tweets = await client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=1)
#
#     existing_tweet_ids = {str(post.tweet_id) for post in Post.query.all()}
#     new_tweets = []
#
#     for tweet in tweets:
#         if str(tweet.id) in existing_tweet_ids:
#             continue
#
#         parsed_date = parse_twitter_datetime(tweet.created_at)
#         if not parsed_date:
#             print(f"❌ 트윗 {tweet.id} 날짜 파싱 실패로 저장되지 않음")
#             continue
#
#         translated_data = await translate_japanese_tweet(tweet.full_text, parsed_date)
#
#         included_dt = None
#         if translated_data["datetime"]:
#             try:
#                 included_dt = datetime.strptime(translated_data["datetime"], "%Y.%m.%d %H:%M:%S")
#             except Exception as e:
#                 print(f"❌ included_date 파싱 오류: {translated_data['datetime']} → {e}")
#
#         new_post = Post(
#             tweet_id=tweet.id,
#             tweet_userid=str(user_id),
#             tweet_username=username,
#             tweet_date=parsed_date,
#             tweet_included_date=included_dt,
#             tweet_text=tweet.full_text,
#             tweet_translated_text=translated_data["translated"],
#             tweet_about=translated_data["category"]
#         )
#         db.session.add(new_post)
#         new_tweets.append({
#             "tweet_id": tweet.id,
#             "tweet_text": tweet.full_text,
#             "translated": translated_data["translated"],
#             "datetime": translated_data["datetime"],
#             "category": translated_data["category"]
#         })
#
#     db.session.commit()
#     return new_tweets


# import json
# import os
# from twikit import Client
# from models import db, Post
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# COOKIE_FILE = os.path.join(BASE_DIR, "..", "config", "twitter_cookies.json")
# client = Client('en-US')
#
# logged_in = False  # 로그인 상태 추적
#
# async def ensure_login():
#     global logged_in
#     if logged_in:
#         return
#     await load_cookies_and_login()
#     logged_in = True
#
# async def load_cookies_and_login():
#     if os.path.exists(COOKIE_FILE):
#         with open(COOKIE_FILE, "r") as f:
#             cookies = json.load(f)
#         client.set_cookies(cookies)
#         print("\u2705 Login Successfully using cookies")
#     else:
#         raise FileNotFoundError("\ud83d\udea8 No cookie file found. Please log in again.")
#
# async def get_user_id(screen_name: str):
#     user = await client.get_user_by_screen_name(screen_name)
#     return user.id, user.name
#
# def parse_twitter_datetime(dt_str):
#     try:
#         return datetime.strptime(dt_str, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d %H:%M:%S")
#     except Exception as e:
#         print(f"\u274c \ub0a0\uc9dc \ud30c\uc2f1 \uc2e4\ud328: {dt_str} \u2192 {e}")
#         return None
#
# async def fetch_and_store_latest_tweets(screen_name: str):
#     await ensure_login()
#     user_id, username = await get_user_id(screen_name)
#
#     tweets = await client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=50)
#
#     existing_tweet_ids = {str(post.tweet_id) for post in Post.query.all()}
#     new_tweets = []
#
#     for tweet in tweets:
#         if str(tweet.id) in existing_tweet_ids:
#             continue
#
#         parsed_date = parse_twitter_datetime(tweet.created_at)
#         if not parsed_date:
#             print(f"\u274c \ud2b8\uc717 {tweet.id} \ub0a0\uc9dc \ud30c\uc2f1 \uc2e4\ud328\ub85c \uc800\uc7a5\ub418\uc9c0 \uc54a\uc74c")
#             continue
#
#         translated_data = await translate_japanese_tweet(tweet.full_text, parsed_date)
#
#         included_dt = None
#         if translated_data["datetime"]:
#             try:
#                 included_dt = datetime.strptime(translated_data["datetime"], "%Y.%m.%d %H:%M:%S")
#             except Exception as e:
#                 print(f"\u274c included_date \ud30c\uc2f1 \uc624\ub958: {translated_data['datetime']} \u2192 {e}")
#
#         new_post = Post(
#             tweet_id=tweet.id,
#             tweet_userid=str(user_id),
#             tweet_username=username,
#             tweet_date=parsed_date,
#             tweet_included_date=included_dt,
#             tweet_text=tweet.full_text,
#             tweet_translated_text=translated_data["translated"],
#             tweet_about=translated_data["category"]
#         )
#         db.session.add(new_post)
#         new_tweets.append(new_post)
#
#     if new_tweets:
#         db.session.commit()
#         print(f"\u2705 {len(new_tweets)}\uac1c\uc758 \uc0c8 \ud2b8\uc717 \uc800\uc7a5 \uc644\ub8cc")
#
#     # 최신순 정렬된 DB 데이터 20개 반환
#     recent_posts = Post.query.order_by(Post.tweet_date.desc()).limit(20).all()
#     return [
#         {
#             "tweet_id": str(post.tweet_id),
#             "tweet_userid": post.tweet_userid,
#             "tweet_username": post.tweet_username,
#             "tweet_date": post.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
#             "tweet_included_date": post.tweet_included_date.strftime("%Y-%m-%d %H:%M:%S") if post.tweet_included_date else None,
#             "tweet_text": post.tweet_text,
#             "tweet_translated_text": post.tweet_translated_text,
#             "tweet_about": post.tweet_about
#         } for post in recent_posts
#     ]





from datetime import datetime
from services.openai_translator import translate_japanese_tweet
from repository.tweet_repository import TweetRepository
from services.tweet_client_service import TwitterClientService

class TweetService:
    def __init__(self):
        self.repo = TweetRepository()
        self.twitter_client = TwitterClientService()

    async def fetch_and_store_latest_tweets(self, screen_name: str):
        await self.twitter_client.ensure_login()
        user_id, username = await self.twitter_client.get_user_id(screen_name)

        tweets = await self.twitter_client.get_user_tweets(user_id=user_id, count=50)
        print(f"🌐 {len(tweets)}개의 트윗 수신됨")
        existing_ids = self.repo.get_existing_tweet_ids()
        new_posts = []

        for tweet in tweets:
            if str(tweet.id) in existing_ids:
                print(f"⛔ 중복된 트윗 무시: {tweet.id}")
                continue

            parsed_date = self._parse_twitter_datetime(tweet.created_at)
            if not parsed_date:
                print(f"⛔ 트윗 {tweet.id} 날짜 파싱 실패로 저장 안 됨")
                continue

            translated_data = await translate_japanese_tweet(tweet.full_text, parsed_date)

            included_dt = None
            if translated_data["datetime"]:
                try:
                    included_dt = datetime.strptime(translated_data["datetime"], "%Y.%m.%d %H:%M:%S")
                except Exception as e:
                    print(f"⚠️ included_date 파싱 실패: {translated_data['datetime']} → {e}")

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
            print(f"✅ {len(new_posts)}개의 새 트윗 저장 완료")

        recent_posts = self.repo.get_recent_posts(limit=20)
        return [
            {
                "tweet_id": str(p.tweet_id),
                "tweet_userid": p.tweet_userid,
                "tweet_username": p.tweet_username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_included_date": p.tweet_included_date.strftime("%Y-%m-%d %H:%M:%S") if p.tweet_included_date else None,
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about": p.tweet_about
            } for p in recent_posts
        ]

    def _parse_twitter_datetime(self, dt_str: str) -> str | None:
        try:
            return datetime.strptime(dt_str, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"⛔ 날짜 파싱 실패: {dt_str} → {e}")
            return None



