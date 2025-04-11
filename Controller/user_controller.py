from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.user_service import UserService

user_bp = Blueprint("user", __name__)
user_service = UserService()

# 트위터 유저 데이터 조회
@user_bp.route("/user", methods=["GET"])
def get_user():
    tweet_id = request.args.get("tweet_id")
    if not tweet_id:
        return jsonify({"error": "tweet_id is required"}), 400

    user_info = user_service.get_user_info(tweet_id)
    if not user_info:
        return jsonify({"error": "Failed to fetch Twitter user data"}), 404

    return jsonify(user_info), 200

# 현재 로그인한 유저의 트위터 Id 조회
@user_bp.route("/user/tweet_id", methods=["GET"])
@jwt_required()
def get_logged_in_user_tweet_id():
    user_email = get_jwt_identity()
    tweet_id = user_service.get_user_tweet_id(user_email)
    if not tweet_id:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"tweetId": tweet_id}), 200

# 현재 로그인한 유저의 오시 정보 조회
@user_bp.route("/user/oshi", methods=["GET"])
@jwt_required()
def get_oshi():
    user_email = get_jwt_identity()
    result = user_service.get_oshi(user_email)
    if not result:
        return jsonify({"error": "No oshi registered"}), 404
    return jsonify(result), 200

# 현재 로그인한 유저의 오시 등록
@user_bp.route("/user/oshi", methods=["POST"])
@jwt_required()
def set_oshi():
    user_email = get_jwt_identity()
    data = request.get_json()
    oshi_tweet_id = data.get("oshi_tweet_id")

    if not oshi_tweet_id:
        return jsonify({"error": "오시 트윗 ID가 제공되지 않았습니다."}), 400

    success, message = user_service.set_oshi(user_email, oshi_tweet_id)
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message, "oshi_tweet_id": oshi_tweet_id}), 200