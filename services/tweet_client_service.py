import os
import json
from twikit import Client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "..", "config", "twitter_cookies.json")

# 트위터 로그인 로직 관리
class TwitterClientService:
    def __init__(self):
        self.client = Client("en-US")
        self.logged_in = False

    ## Client가 없다면 생성
    async def ensure_login(self):
        if not self.logged_in:
            await self._load_cookies_and_login()
            self.logged_in = True

    ## 쿠키를 통해 트위터 로그인
    async def _load_cookies_and_login(self):
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            self.client.set_cookies(cookies)
            print("Login Successfully using cookies")
        else:
            raise FileNotFoundError("No cookie file found. Please log in again.")

    ## 로그인 되어있는 Client 객체 반환
    def get_client(self) -> Client:
        return self.client