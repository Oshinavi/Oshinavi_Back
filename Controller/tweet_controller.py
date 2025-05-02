from flask import Blueprint, jsonify, request
from services.tweet_service import TweetService
import asyncio

tweet_bp = Blueprint("tweet", __name__)
tweet_service = TweetService()

# 트윗 가져오기
@tweet_bp.route("/tweets/<string:screen_name>", methods=["GET"])
def fetch_user_tweets(screen_name):
    print(f"📡 [ROUTE] /tweets/{screen_name} 호출됨")
    try:
        # 비동기 서비스 호출을 안전하게 감싸기
        tweets = asyncio.run(tweet_service.fetch_and_store_latest_tweets(screen_name))
        return jsonify(tweets), 200
    except Exception as e:
        print(f"Error in /tweets/{screen_name}: {e}")
        return jsonify({"error": str(e)}), 500

# 자동 리플라이 생성
@tweet_bp.route("/tweets/reply/auto_generate", methods=["POST"])
def auto_generate_tweet_reply():
    try:
        data = request.get_json()
        tweet_text = data.get("tweet_text")
        if not tweet_text:
            return jsonify({"error": "전달된 트윗 텍스트가 없습니다"}), 400

        generated_reply = asyncio.run(tweet_service.generate_auto_reply(tweet_text))
        if generated_reply:
            return jsonify(generated_reply), 200
        else:
            return jsonify({"error": "답변 생성에 실패했습니다"}), 400

    except Exception as e:
        print(f"Error in reply generator API: {e}")
        return jsonify({"success": False, "error": f"서버 오류: {str(e)}"}), 500

# 리플라이 보내기
@tweet_bp.route("/tweets/reply/<string:tweet_id>", methods=["POST"])
def send_tweet_reply(tweet_id):
    try:
        data = request.get_json()
        tweet_text = data.get("tweet_text")

        if not tweet_text:
            return jsonify({"success": False, "error": "트윗 텍스트가 제공되지 않았습니다."}), 400

        result = asyncio.run(tweet_service.send_reply(tweet_id, tweet_text))

        if result.get("success"):
            return jsonify({"success": True, "message": result.get("message")}), 200
        else:
            return jsonify({"success": False, "error": result.get("error")}), 400

    except Exception as e:
        print(f"Error in reply API: {e}")
        return jsonify({"success": False, "error": f"서버 오류: {str(e)}"}), 500


# @tweet_bp.route("/tweets/like>", methods=["POST"])
# async def like_tweets(tweet_id, tweet_userid):