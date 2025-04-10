import asyncio
import json
import os
import csv
from twikit import Client
from datetime import datetime, timezone

# 설정 값
COOKIE_FILE = "../../X_Translator/config/twitter_cookies.json"
CSV_FILE = "../csv/tweets_3.csv"
SCREENNAME = "Hayama_Fuka"

# TARGET_DATE를 오프셋이 있는 datetime으로 변환
TARGET_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)

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


async def save_tweets_to_csv(tweets):
    """ 트윗을 CSV 파일에 저장, 중복 트윗은 저장하지 않음 """
    existing_tweets = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                existing_tweets.add(row[1])  # 트윗 내용 중복 확인

    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(['Created At', 'Screen Name', 'Tweet Text'])

        for tweet in tweets:
            if tweet.text not in existing_tweets:
                cleaned_text = tweet.text.replace("\n", " ").replace("\r", " ")
                writer.writerow([tweet.created_at, tweet.user.screen_name, cleaned_text])
                existing_tweets.add(tweet.text)
                print(f"📝 [{tweet.user.screen_name}] - {tweet.created_at}")
                print(f"{cleaned_text}\n")


async def fetch_and_save_tweets():
    """ 트윗을 가져와서 저장 """
    await load_cookies_and_login()
    user_id = await get_user_id()

    latest_time = datetime.now(timezone.utc)  # 현재 시간
    cursor = None  # 초기 cursor 설정 없음

    empty_response_count = 0  # 연속 빈 응답 개수

    while latest_time > TARGET_DATE:
        try:
            # 트윗 가져오기 (20개씩)
            tweets = await client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=20, cursor=cursor)

            if not tweets:
                empty_response_count += 1
                print(f"🚨 No tweets found ({empty_response_count}/3)")

                if empty_response_count >= 3:
                    print("⛔ Too many empty responses. Stopping...")
                    break  # 3회 연속 빈 응답이면 종료

                await asyncio.sleep(10)  # 10초 후 다시 시도
                continue

            empty_response_count = 0  # 트윗이 있으면 카운트 초기화
            filtered_tweets = []

            for tweet in tweets:
                tweet_time = datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y")
                if tweet_time < TARGET_DATE:
                    print("⏳ Reached the target date, stopping...")
                    break  # TARGET_DATE 이전이면 중단
                filtered_tweets.append(tweet)

            # 트윗 저장
            if filtered_tweets:
                await save_tweets_to_csv(filtered_tweets)
                latest_time = datetime.strptime(filtered_tweets[-1].created_at, "%a %b %d %H:%M:%S %z %Y")

            # 새로운 cursor 업데이트
            new_cursor = tweets.next_cursor
            if new_cursor is None:
                print("🚨 No more tweets to fetch. Stopping...")
                break  # 더 이상 가져올 트윗이 없으면 종료
            elif new_cursor == cursor:
                print("⚠️ Cursor did not change, retrying with None")
                cursor = None  # 같은 cursor가 반복되면 None으로 초기화
            else:
                cursor = new_cursor  # 정상적인 cursor 업데이트

            print(f"🔄 New cursor: {cursor}")

            await asyncio.sleep(2 * 60)  # 요청 속도 제한 고려 (2분 대기)

        except Exception as e:
            print(f"⚠️ Error occurred: {e}")
            await asyncio.sleep(10)  # 오류 발생 시 10초 대기 후 재시도


async def main():
    await fetch_and_save_tweets()


asyncio.run(main())