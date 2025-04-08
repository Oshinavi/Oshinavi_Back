from flask import jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from repository.user_repository import (
    find_user_by_email,
    create_user,
    create_tweet_user
)
from utils.twitter_client import get_twitter_id_by_username
from flask_jwt_extended import create_access_token

def signup_user(data):
    required_fields = ["username", "email", "password", "cfpassword", "tweetId"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if data["password"] != data["cfpassword"]:
        return jsonify({"error": "Passwords do not match"}), 400

    if find_user_by_email(data["email"]):
        return jsonify({"error": "User already exists"}), 409

    # 트위터 ID 확인
    tweet_internal_id = get_twitter_id_by_username(data["tweetId"])
    if tweet_internal_id is None:
        return jsonify({"error": "존재하지 않는 유저입니다"}), 404

    user = create_user(
        username=data["username"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        tweet_id=data["tweetId"]
    )

    create_tweet_user(user_id=user.id, tweet_id=data["tweetId"], tweet_internal_id=tweet_internal_id)
    return jsonify({"message": "회원가입 성공"}), 201

def login_user(data):
    user = find_user_by_email(data.get("email"))
    if user and check_password_hash(user.password, data.get("password")):
        token = create_access_token(identity=user.email)
        return jsonify({"message": "로그인 성공", "token": token}), 200
    return jsonify({"error": "Invalid username or password"}), 401

def logout_user():
    return jsonify({"message": "로그아웃 성공"}), 200