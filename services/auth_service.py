from flask import jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from repository.user_repository import UserRepository
from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from utils.async_utils import run_async

user_repo = UserRepository()

# 유저 회원가입
def signup_user(data):
    required_fields = ["username", "email", "password", "cfpassword", "tweetId"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if data["password"] != data["cfpassword"]:
        return jsonify({"error": "Passwords do not match"}), 400

    if user_repo.find_user_by_email(data["email"]):
        return jsonify({"error": "User already exists"}), 409

    # 트위터 ID 확인
    twitter_client = TwitterClientService()
    twitter_user = TwitterUserService(twitter_client)

    if not run_async(twitter_user.user_exists(data["tweetId"])):
        return jsonify({"error": "User does not exist"}), 404

    try:
        tweet_internal_id = run_async(twitter_user.get_user_id(data["tweetId"]))
    except Exception:
        return jsonify({"error": "존재하지 않는 유저입니다"}), 404

    existing_user = user_repo.get_twitter_user_by_internal_id(tweet_internal_id)
    if not existing_user:
        user_repo.create_twitter_user(
            twitter_internal_id=tweet_internal_id,
            twitter_id=data["tweetId"],
            username=data["username"]
        )

    user = user_repo.create_user(
        username=data["username"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        twitter_user_internal_id=tweet_internal_id
    )

    return jsonify({"message": "회원가입 성공"}), 201

# 유저 로그인
def login_user(data):
    user = user_repo.find_user_by_email(data.get("email"))
    if user and check_password_hash(user.password, data.get("password")):
        token = create_access_token(identity=user.email)
        return jsonify({"message": "로그인 성공", "token": token}), 200
    return jsonify({"error": "Invalid username or password"}), 401

# 유저 로그아웃
def logout_user():
    return jsonify({"message": "로그아웃 성공"}), 200