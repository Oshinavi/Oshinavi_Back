# from flask import Blueprint, request, jsonify
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from models import User, db, UserOshi
# from services.tweet_user_service import TwitterUserService
# from utils.async_utils import run_async
# from services.tweet_client_service import TwitterClientService
#
# user_bp = Blueprint("user", __name__)
#
# # 서비스 인스턴스 생성
# twitter_client_service = TwitterClientService()
# twitter_user_service = TwitterUserService(twitter_client_service)
#
# # 트위터 유저 정보 조회 API
# @user_bp.route("/user", methods=["GET"])
# def get_user():
#     tweet_id = request.args.get("tweet_id")
#
#     if not tweet_id:
#         return jsonify({"error": "tweet_id is required"}), 400
#
#     twitter_data = run_async(twitter_user_service.get_user_info(tweet_id))
#     if not twitter_data:
#         return jsonify({"error": "Failed to fetch Twitter user data"}), 404
#
#     return jsonify({
#         "tweet_internal_id": twitter_data["id"],
#         "tweet_id": tweet_id,
#         "username": twitter_data["username"],
#         "bio": twitter_data["bio"],
#     }), 200
#
# # 현재 로그인한 유저의 트윗 ID 반환
# @user_bp.route("/user/tweet_id", methods=["GET"])
# @jwt_required()
# def get_logged_in_user_tweet_id():
#     print("✅ /user/tweet_id 호출됨")
#     user_email = get_jwt_identity()
#     print(f"현재 로그인한 유저 ID: {user_email}")
#
#     user = User.query.filter_by(email=user_email).first()
#     if not user:
#         return jsonify({"error": "User not found"}), 404
#
#     return jsonify({
#         "tweetId": user.tweet_id
#     }), 200
#
# # 오시 정보 가져오기
# @user_bp.route("/user/oshi", methods=["GET"])
# @jwt_required()
# def get_oshi():
#     email = get_jwt_identity()
#     print(f"🔍 요청한 사용자 ID: {email}")
#     user = User.query.filter_by(email=email).first()
#
#     if not user:
#         return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404
#
#     user_oshi = UserOshi.query.filter_by(id=user.id).first()
#     print(f"🔎 찾은 오시 정보: {user_oshi.oshi_tweet_id if user_oshi else '없음'}")
#
#     if not user_oshi:
#         return jsonify({"error": "No oshi registered"}), 404
#
#     return jsonify({
#         "oshi_tweet_id": user_oshi.oshi_tweet_id,
#         "oshi_username": user_oshi.oshi_username
#     }), 200
#
# # 오시 설정
# @user_bp.route("/user/oshi", methods=["POST"])
# @jwt_required()
# def set_oshi():
#     data = request.get_json()
#     user_email = get_jwt_identity()
#     oshi_tweet_id = data.get("oshi_tweet_id")
#
#     if not oshi_tweet_id:
#         return jsonify({"error": "오시 트윗 ID가 제공되지 않았습니다."}), 400
#
#     # 유효한 유저인지 확인
#     is_valid = run_async(twitter_user_service.user_exists(oshi_tweet_id))
#     if not is_valid:
#         return jsonify({"error": "No such user exists"}), 400
#
#     # 유저 정보 가져오기
#     user_info = run_async(twitter_user_service.get_user_info(oshi_tweet_id))
#     if not user_info:
#         return jsonify({"error": "Failed to retrieve user info"}), 500
#
#     oshi_username = user_info["username"]
#
#     # DB에서 현재 로그인 유저 조회
#     user = User.query.filter_by(email=user_email).first()
#     if not user:
#         return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404
#
#     # 오시 정보 등록 or 업데이트
#     user_oshi = UserOshi.query.filter_by(id=user.id).first()
#     if user_oshi:
#         user_oshi.oshi_tweet_id = oshi_tweet_id
#         user_oshi.oshi_username = oshi_username
#     else:
#         user_oshi = UserOshi(id=user.id, oshi_tweet_id=oshi_tweet_id, oshi_username=oshi_username)
#         db.session.add(user_oshi)
#
#     db.session.commit()
#
#     return jsonify({
#         "message": "오시 트윗 ID가 성공적으로 업데이트되었습니다.",
#         "oshi_tweet_id": oshi_tweet_id
#     }), 200