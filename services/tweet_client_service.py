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
            await self._load_cookies_and_login()
            self.logged_in = True

    async def _load_cookies_and_login(self):
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            self.client.set_cookies(cookies)
            print("✅ Login Successfully using cookies")
        else:
            raise FileNotFoundError("🚨 No cookie file found. Please log in again.")

    def get_client(self) -> Client:
        return self.client