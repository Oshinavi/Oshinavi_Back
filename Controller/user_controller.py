from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.user_service import UserService
from services.exceptions import ApiError, BadRequestError

user_bp = Blueprint("users", __name__                                                       )
user_service = UserService()

# 트위터 유저 데이터 조회
@user_bp.route("", methods=["GET"])
def get_user():
    tweet_id = request.args.get("tweet_id")
    if not tweet_id:
        # 쿼리 파라미터 누락은 BadRequestError 로 처리
        return BadRequestError("tweet_id is required").to_response()

    try:
        user_info = user_service.get_user_info(tweet_id)
        return jsonify(user_info), 200

    except ApiError as e:
        # NotFoundError 등 서비스에서 던진 예외를 그대로 HTTP 응답으로 변환
        return e.to_response()

# 현재 로그인한 유저의 트위터 Id 조회
@user_bp.route("/tweet_id", methods=["GET"])
@jwt_required()
def get_logged_in_user_tweet_id():
    user_email = get_jwt_identity()
    try:
        tweet_id = user_service.get_user_tweet_id(user_email)
        return jsonify({"tweetId": tweet_id}), 200

    except ApiError as e:
        return e.to_response()

# 현재 로그인한 유저의 오시 정보 조회
@user_bp.route("/oshi", methods=["GET"])
@jwt_required()
def get_oshi():
    user_email = get_jwt_identity()
    try:
        result = user_service.get_oshi(user_email)
        return jsonify(result), 200

    except ApiError as e:
        return e.to_response()

# 현재 로그인한 유저의 오시 등록
@user_bp.route("/oshi", methods=["POST"])
@jwt_required()
def set_oshi():
    user_email = get_jwt_identity()
    data = request.get_json() or {}
    oshi_tweet_id = data.get("oshi_tweet_id")

    if not oshi_tweet_id:
        return BadRequestError("오시 트윗 ID가 제공되지 않았습니다.").to_response()

    try:
        # 변경된 signiture 에 따라 None 반환 → 정상, 예외 던지면 실패
        user_service.set_oshi(user_email, oshi_tweet_id)
        return jsonify({
            "message": "오시 정보가 성공적으로 저장되었습니다.",
            "oshi_tweet_id": oshi_tweet_id
        }), 200

    except ApiError as e:
        return e.to_response()