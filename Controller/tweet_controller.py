# from flask import Blueprint, jsonify
# from services.tweet_service import fetch_and_store_latest_tweets
# import asyncio
#
# tweet_bp = Blueprint("tweet", __name__)
#
# @tweet_bp.route("/tweets/<string:screen_name>", methods=["GET"])
# def fetch_user_tweets(screen_name):
#     try:
#         tweets = asyncio.run(fetch_and_store_latest_tweets(screen_name))
#         return jsonify(tweets), 200
#     except Exception as e:
#         print(f"❌ Error in /tweets/{screen_name}: {e}")
#         return jsonify({"error": str(e)}), 500




from flask import Blueprint, jsonify
from services.tweet_service import TweetService
import asyncio

tweet_bp = Blueprint("tweet", __name__)
tweet_service = TweetService()

@tweet_bp.route("/tweets/<string:screen_name>", methods=["GET"])
def fetch_user_tweets(screen_name):
    print(f"📡 [ROUTE] /tweets/{screen_name} 호출됨")
    try:
        # 비동기 서비스 호출을 안전하게 감싸기
        tweets = asyncio.run(tweet_service.fetch_and_store_latest_tweets(screen_name))
        return jsonify(tweets), 200
    except Exception as e:
        print(f"❌ Error in /tweets/{screen_name}: {e}")
        return jsonify({"error": str(e)}), 500

# @tweet_bp.route("/tweets/like>", methods=["POST"])
# async def like_tweets(tweet_id, tweet_userid):