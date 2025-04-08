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
from sqlalchemy.util import await_only

from services.tweet_service import fetch_and_store_latest_tweets
import asyncio

tweet_bp = Blueprint("tweet", __name__)

@tweet_bp.route("/tweets/<string:screen_name>", methods=["GET"])
async def fetch_user_tweets(screen_name):
    try:
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        tweets = await fetch_and_store_latest_tweets(screen_name)
        return jsonify(tweets), 200
    except Exception as e:
        print(f"❌ Error in /tweets/{screen_name}: {e}")
        return jsonify({"error": str(e)}), 500