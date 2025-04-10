import asyncio
import json
import os
import csv
from twikit import Client
from datetime import datetime, timezone

# 설정 값
COOKIE_FILE = "../../X_Translator/config/twitter_cookies.json"
CSV_FILE = "../csv/tweets_3.csv"
SCREENNAME = "Shumo_dev"

# TARGET_DATE를 오프셋이 있는 datetime으로 변환
TARGET_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)


async def main():
    # 쿠키 로드
    if not os.path.exists(COOKIE_FILE):
        print("Error: Twitter 쿠키 파일이 존재하지 않습니다.")
        return

    with open(COOKIE_FILE, "r") as f:
        cookies = json.load(f)

    # 클라이언트 초기화
    client = Client('en-US', cookies=cookies)

    # 사용자 ID 가져오기
    user_info = await client.get_user_by_screen_name(SCREENNAME)
    user_id = user_info.id
    print(f"User ID: {user_id}")

    # 트윗 작성
    await client.create_tweet(text="hello", reply_to="1901315712414814423")


# asyncio 실행
asyncio.run(main())