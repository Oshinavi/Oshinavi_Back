from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, db, UserOshi
from utils.async_utils import run_async
from routes.tweet_profile_controller import get_userinfo_by_username, isUserExist
from services.tweet_service import get_user_id

user_bp = Blueprint("user", __name__)

@user_bp.route("/user", methods=["GET"])
def get_user():
    tweet_id = request.args.get("tweet_id")

    if not tweet_id:
        return jsonify({"error": "tweet_id is required"}), 400

    # 1. 우선 트위터에서 유저 정보 조회
    twitter_data = run_async(get_userinfo_by_username(tweet_id))
    if not twitter_data:
        return jsonify({"error": "Failed to fetch Twitter user data"}), 404

    tweet_internal_id, username, bio = twitter_data

    return jsonify({
        "tweet_internal_id": tweet_internal_id,
        "tweet_id": tweet_id,
        "username": username,
        "bio": bio,
    }), 200

@user_bp.route("/user/tweet_id", methods=["GET"])
@jwt_required()
def get_logged_in_user_tweet_id():
    print("✅ /user/tweet_id 호출됨")
    user_email = get_jwt_identity()
    print(f"현재 로그인한 유저 ID: {user_email}")

    user = User.query.filter_by(email=user_email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "tweetId": user.tweet_id
    }), 200

@user_bp.route("/user/oshi", methods=["GET"])
@jwt_required()
def get_oshi():
    email = get_jwt_identity()
    print(f"🔍 요청한 사용자 ID: {email}")
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

    user_oshi = UserOshi.query.filter_by(id=user.id).first()
    print(f"🔎 찾은 오시 정보: {user_oshi.oshi_tweet_id if user_oshi else '없음'}")

    if not user_oshi:
        return jsonify({"error": "No oshi registered"}), 404

    return jsonify({
        "oshi_tweet_id": user_oshi.oshi_tweet_id,
        "oshi_username": user_oshi.oshi_username
    }), 200


@user_bp.route("/user/oshi", methods=["POST"])
@jwt_required()
def set_oshi():
    data = request.get_json()
    user_email = get_jwt_identity()
    oshi_tweet_id = data.get("oshi_tweet_id")

    if not oshi_tweet_id:
        return jsonify({"error": "오시 트윗 ID가 제공되지 않았습니다."}), 400

    is_valid = run_async(isUserExist(oshi_tweet_id))
    if not is_valid:
        return jsonify({"error": "No such user exists"}), 400

    uid, username = run_async(get_user_id(oshi_tweet_id))
    oshi_username = username

    # 이메일로 사용자 조회
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

    # oshi 등록 또는 업데이트
    user_oshi = UserOshi.query.filter_by(id=user.id).first()
    if user_oshi:
        user_oshi.oshi_tweet_id = oshi_tweet_id
        user_oshi.oshi_username = oshi_username
    else:
        user_oshi = UserOshi(id=user.id, oshi_tweet_id=oshi_tweet_id, oshi_username=oshi_username)
        db.session.add(user_oshi, oshi_username)

    db.session.commit()

    return jsonify({"message": "오시 트윗 ID가 성공적으로 업데이트되었습니다.",
                    "oshi_tweet_id": oshi_tweet_id
                    }), 200