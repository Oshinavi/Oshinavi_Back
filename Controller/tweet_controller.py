import asyncio
from flask import Blueprint, request, jsonify
from services.exceptions import ApiError, BadRequestError
from services.tweet_service import TweetService

tweet_bp = Blueprint("tweets", __name__)
tweet_service = TweetService()

# 트윗 가져오기
@tweet_bp.route("/<string:screen_name>", methods=["GET"])
def fetch_user_tweets(screen_name):
    print(f"📡 [ROUTE] /tweets/{screen_name} 호출됨")
    try:
        # 비동기 서비스 호출을 안전하게 감싸기
        tweets = asyncio.run(
            tweet_service.fetch_and_store_latest_tweets(screen_name)
        )
        return jsonify(tweets), 200

    # 에러 반환
    except ApiError as e:
        return e.to_response()

    # Unexpected error 처리
    except Exception as e:
        print(f"Unexpected error in fetch_user_tweets: {e}")
        return jsonify({"error": "서버 오류"}), 500

# 자동 리플라이 생성
@tweet_bp.route("/reply/auto_generate", methods=["POST"])
def auto_generate_tweet_reply():
    try:
        data = request.get_json()
        tweet_text = data.get("tweet_text")
        if not tweet_text:
            raise BadRequestError("전달된 트윗 텍스트가 없습니다")

        generated_reply = asyncio.run(tweet_service.generate_auto_reply(tweet_text))
        return jsonify({"reply": generated_reply}), 200


    # 에러 반환
    except ApiError as e:
        return e.to_response()

    # Unexpected error 처리
    except Exception as e:
        print(f"Unexpected error in reply generator API: {e}")
        return jsonify({"error": "서버 오류"}), 500


# 리플라이 보내기
@tweet_bp.route("/reply/<string:tweet_id>", methods=["POST"])
def send_tweet_reply(tweet_id):
    try:
        data = request.get_json() or {}
        tweet_text = data.get("tweet_text")
        if not tweet_text:
            raise BadRequestError("리플라이할 텍스트가 제공되지 않았습니다.")

        result = asyncio.run(
            tweet_service.send_reply(tweet_id, tweet_text)
        )
        # service.send_reply()는 {"success":bool, "message":str, ...} 형태로 반환
        status = 200 if result.get("success") else 400
        return jsonify(result), status

    # 에러 반환
    except ApiError as e:
        return e.to_response()

    # Unexpected error 처리
    except Exception as e:
        print(f"Unexpected error in send_tweet_reply: {e}")
        return jsonify({"error": "서버 오류"}), 500


# @tweet_bp.route("/like>", methods=["POST"])
# async def like_tweets(tweet_id, tweet_userid):