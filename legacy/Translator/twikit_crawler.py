import asyncio
import json
import os
import csv
from twikit import Client
from datetime import datetime, timezone

# 설정 값
COOKIE_FILE = "../../X_Translator/config/twitter_cookies.json"
CSV_FILE = "../../X_Translator/csv/tweets_test_link.csv"
SCREENNAME = "hasunosora_SIC"

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
        # 쿠키를 클라이언트 세션에 적용
        client.set_cookies(cookies)
        print("✅ Login Successfully using cookies")
    else:
        raise FileNotFoundError("🚨 No cookie file found. Please log in again.")


async def save_tweets_to_csv(tweets):
    """ 트윗을 CSV 파일에 저장, 중복 트윗은 저장하지 않음 """
    existing_tweets = set()
    if os.path.exists(CSV_FILE):
        # 이미 존재하는 트윗 읽어오기
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                existing_tweets.add(row[1])  # 트윗 내용만 중복 확인

    # 새로 가져온 트윗을 파일에 추가
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # 첫 번째 라인에 헤더가 없다면 작성
        if f.tell() == 0:
            writer.writerow(['Tweet URL', 'Created At', 'Screen Name', 'Tweet Text'])

        for tweet in tweets:
            if tweet.text not in existing_tweets:
                # 텍스트에 줄바꿈이 있으면 공백으로 대체
                cleaned_text = tweet.text.replace("\n", " ").replace("\r", " ")

                # 트윗 링크 생성
                tweet_url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}"

                # CSV 파일에 저장
                writer.writerow([tweet_url, tweet.created_at, tweet.user.screen_name, cleaned_text])
                existing_tweets.add(tweet.text)

                # 트윗을 읽을 때마다 출력
                print(f"📝 [{tweet.user.screen_name}] - {tweet.created_at}")
                print(f"{cleaned_text}\n")
                print(f"Link: {tweet_url}\n")


async def fetch_and_save_tweets():
    """ 트윗을 15분마다 가져와서 저장 """
    await load_cookies_and_login()
    user_id = await get_user_id()

    # 현재 시간부터 2023.01.01 시점까지 트윗 가져오기
    latest_time = datetime.now(timezone.utc)  # UTC 시간으로 변환
    cursor = None

    while True: #latest_time > TARGET_DATE:
        # 20개의 트윗 가져오기
        tweets = await client.get_user_tweets(user_id=user_id, tweet_type='Tweets', count=20, cursor=cursor)

        # 가져온 트윗 필터링 (작성 시간이 TARGET_DATE 이전이면 종료)
        filtered_tweets = []
        for tweet in tweets:
            tweet_time = datetime.strptime(tweet.created_at, "%a %b %d %H:%M:%S %z %Y")
            # if tweet_time >= TARGET_DATE:
            filtered_tweets.append(tweet)
            # else:
            #    break  # 더 이상 2023.01.01 이전의 트윗은 가져오지 않음
            print(tweet.text)

        # 트윗을 CSV 파일에 저장
        if filtered_tweets:
            await save_tweets_to_csv(filtered_tweets)

        # 마지막 트윗의 작성 시간으로 업데이트 (다음 요청을 위해)
        if filtered_tweets:
            latest_time = datetime.strptime(filtered_tweets[-1].created_at, "%a %b %d %H:%M:%S %z %Y")

        # 15분 대기 후 다시 트윗 가져오기
        cursor = tweets.next_cursor
        print(cursor)
        if cursor is None:
            print("🚨 No more tweets to fetch. Stopping...")
            break  # 더 이상 가져올 트윗이 없으면 루프 종료
        await asyncio.sleep(1 * 60)  # 지정 시간동안 대기


async def main():
    # 트윗 가져오기 및 저장 시작
    await fetch_and_save_tweets()


asyncio.run(main())