import aiofiles
from twikit import Client
import asyncio
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 현재 파일이 위치한 디렉토리
COOKIE_FILE = os.path.join(BASE_DIR, "..", "config", "twitter_cookies.json")

client = Client('en-US')


async def load_cookies_and_login():
    """ 저장된 쿠키를 불러와 로그인 유지 """
    print(f"🔍 Checking cookie file path: {COOKIE_FILE}")

    file_exists = await asyncio.to_thread(os.path.exists, COOKIE_FILE)
    if file_exists:
        async with aiofiles.open(COOKIE_FILE, "r") as f:
            cookies = json.loads(await f.read())

        print("🔹 Loaded Cookies:", cookies)
        client.set_cookies(cookies)
        print("✅ Login Successfully using cookies")
    else:
        raise FileNotFoundError("🚨 No cookie file found. Please log in again.")