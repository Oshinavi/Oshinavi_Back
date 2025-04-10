import asyncio
import json
import os
import csv
import pytz
from twikit import Client
from datetime import datetime, timezone

# 설정 값
COOKIE_FILE = "../config/twitter_cookies.json"
CSV_FILE = "../csv/tweets_crawled.csv"
SCREENNAME = "hasunosora_SIC"

# UTC+9 시간대 설정
JST = pytz.timezone("Asia/Tokyo")  # UTC+9 (JST/KST)

# 클라이언트 초기화
client = Client('en-US')


async def get_user_id():
    """ 사용자 이름을 ID로 변환 """
    user_info = await client.get_user_by_screen_name(SCREENNAME)
    return user_info.id


async def load_cookies_and_login():
    """ 저장된 쿠키를 불러와 로그인 유지 """
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        client.set_cookies(cookies)
        print("✅ Login Successfully using cookies")
    else:
        raise FileNotFoundError("🚨 No cookie file found. Please log in again.")


def convert_to_jst(utc_time_str):
    """ 트위터 UTC 시간을 UTC+9(JST/KST)로 변환 """
    utc_time = datetime.strptime(utc_time_str, "%a %b %d %H:%M:%S %z %Y")
    jst_time = utc_time.astimezone(JST)  # UTC+9 변환
    return jst_time.strftime("%Y-%m-%d %H:%M:%S %z")  # YYYY-MM-DD HH:MM:SS +0900 형식


def load_latest_tweet_ids():
    """ CSV 파일에서 최신 10개의 트윗 ID를 불러옴 """
    if not os.path.exists(CSV_FILE):
        return set()

    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = list(csv.reader(f))
        if len(reader) <= 1:  # 헤더만 있는 경우
            return set()

        return {row[1] for row in reader[1:21]}  # 상위 10개 트윗 ID 반환


def save_tweets_to_csv(tweets):
    """ 새로운 트윗을 최신순으로 CSV 파일에 저장 """
    if not tweets:
        return

    new_rows = [[convert_to_jst(tweet.created_at), tweet.id, tweet.user.screen_name, tweet.text.replace("\n", " ").replace("\r", " ")]
                for tweet in tweets]

    # 기존 데이터를 읽어와서 최신 트윗을 위에 추가
    existing_data = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            existing_data = list(csv.reader(f))

    # 헤더가 없으면 추가
    if not existing_data:
        existing_data.append(['Created At (UTC+9)', 'Tweet ID', 'Screen Name', 'Tweet Text'])

    # 최신 트윗을 가장 위에 추가한 후 저장
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(existing_data[:1] + new_rows + existing_data[1:])


async def fetch_and_save_tweets():
    """ 15분마다 트윗을 가져와서 CSV에 저장 """
    await load_cookies_and_login()
    user_id = await get_user_id()

    while True:
        # 최신 트윗 10개 가져오기
        tweets = await client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=10)

        if not tweets:
            print("⚠️ No new tweets found.")
        else:
            # CSV의 최신 트윗과 비교하여 중복 여부 확인
            latest_csv_tweet_ids = load_latest_tweet_ids()
            new_tweets = [tweet for tweet in tweets if str(tweet.id) not in latest_csv_tweet_ids]

            if new_tweets:
                print(f"📝 Saving {len(new_tweets)} new tweets.")
                save_tweets_to_csv(new_tweets)
            else:
                print("✅ No new tweets to save, skipping.")

        # 15분 대기 후 다시 실행
        await asyncio.sleep(1 * 60)


async def main():
    """ 메인 실행 함수 """
    await fetch_and_save_tweets()


asyncio.run(main())