import tweepy
import pandas as pd
import schedule
import time
# configure X(Twitter) bearer api token
bearer_token = "AAAAAAAAAAAAAAAAAAAAAL5hzwEAAAAAZVtbtbkRAx9wES7idYBtMAuGEHY%3DBJR0NexAaBzNgvrVNW2Df9HeRAhKWSERxNPumstSy0oKeuBacH"

# generate Tweepy Client
client = tweepy.Client(bearer_token=bearer_token)

tweetdata_csv = "tweetdata.csv"

def updatetweets(username):

    user = client.get_user(username = username)

    if user.data:
        user_id = user.data.id
        print("User ID: ", user_id)

        response = client.get_users_tweets(
            id=user_id,
            max_results=30,
            tweet_fields=["created_at"]
        )
        if response.data:
            tweets_data = [
                {"Tweet ID": tweet.id, "Text": tweet.text, "Created At": tweet.created_at}
                for tweet in response.data
            ]

            try:
                existing_df = pd.read_csv("tweetdata.csv", encoding="utf-8-sig")
            except FileNotFoundError:
                existing_df = pd.DataFrame(columns=["Tweet ID", "Text", "Created At"])

            existing_tweet_ids = set(existing_df["Tweet ID"].astype(str))

            # 중복되지 않은 새로운 트윗 필터링
            unique_tweets = [tweet for tweet in tweets_data if str(tweet["Tweet ID"]) not in existing_tweet_ids]

            if unique_tweets:
                # 새로운 트윗 DataFrame 생성
                new_df = pd.DataFrame(unique_tweets)

                # 기존 데이터 위에 새로운 트윗 추가 (최신 트윗이 상단)
                updated_df = pd.concat([new_df, existing_df], ignore_index=True)

                # CSV 파일 저장
                updated_df.to_csv("tweetdata.csv", index=False, encoding="utf-8-sig")
                print(f"{len(unique_tweets)}개의 새로운 트윗이 추가되었습니다.")
            else:
                print("새로운 트윗이 없습니다.")
        else:
            print("No tweets found.")
    else:
        print("User not found.")

# 15분마다 실행
schedule.every(15).minutes.do(lambda: updatetweets("Hayamasikameshi"))


print("Twitter 데이터 수집을 시작합니다...")
updatetweets("Hayamasikameshi")  # 첫 실행

while True:
    schedule.run_pending()
    time.sleep(1)