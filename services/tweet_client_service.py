import os
import json
from twikit import Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "..", "config", "twitter_cookies.json")

class TwitterClientService:
    def __init__(self):
        self.client = Client("en-US")
        self.logged_in = False

    async def ensure_login(self):
        if not self.logged_in:
            await self.load_cookies_and_login()
            self.logged_in = True

    async def load_cookies_and_login(self):
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            self.client.set_cookies(cookies)
            print("Login Successfully using cookies")
        else:
            raise FileNotFoundError("No cookie file found. Please log in again.")

    def get_client(self) -> Client:
        return self.client

    async def get_user_id(self, screen_name: str):
        user = await self.client.get_user_by_screen_name(screen_name)
        return user.id, user.name

    async def get_user_tweets(self, user_id: str, count: int = 50):
        tweets = await self.client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=count)
        return tweets

    async def get_twitter_id_by_username(username):
        await load_cookies_and_login()
        try:
            user_info = await client.get_user_by_screen_name(username)

            if user_info:
                return user_info.id
            else:
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    async def get_userinfo_by_username(username):
        await load_cookies_and_login()
        try:
            user_info = await client.get_user_by_screen_name(username)

            if user_info:
                return user_info.id, user_info.name, user_info.description
            else:
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    async def isUserExist(username):
        await load_cookies_and_login()
        try:
            user_info = await client.get_user_by_screen_name(username)
            print(f"🔍 user_info for '{username}': {user_info}")

            # 명시적으로 None 체크
            if user_info is None:
                print("🚫 유저 없음 (None 반환)")
                return False

            # user_info가 원하는 필드를 포함하는지 확인
            if hasattr(user_info, "id") and hasattr(user_info, "screen_name"):
                return True
            else:
                print("🚫 예상 구조 아님")
                return False

        except Exception as e:
            print(f"❌ 예외 발생: {e}")
            return False