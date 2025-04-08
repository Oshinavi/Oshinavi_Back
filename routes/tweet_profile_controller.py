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
# # 실제 호출 및 출력
# async def main():
#     username = "Hayama_Fuka"  # '@' 없이 넣기
#     user_info = await get_userinfo_by_username(username)
#
#     if user_info:
#         user_id, name, bio = user_info
#         print("유저 ID:", user_id)
#         print("이름:", name)
#         print("바이오:", bio)
#     else:
#         print("유저 정보를 찾을 수 없습니다.")
#
# # 이벤트 루프 실행
# asyncio.run(main())