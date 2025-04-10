# import asyncio
#
# from flask import Blueprint, request, jsonify
# from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity
# from werkzeug.security import generate_password_hash, check_password_hash
# from models import User, TweetUser, db
# from jwt_blocklist import jwt_blocklist
# from routes.tweet_profile_controller import get_twitter_id_by_username
#
# auth_bp = Blueprint("auth", __name__)
#
# def fetch_twitter_id(tweet_id):
#     loop = asyncio.new_event_loop()  # ✅ 새 이벤트 루프 생성
#     asyncio.set_event_loop(loop)
#     return loop.run_until_complete(get_twitter_id_by_username(tweet_id))  # ✅ 이벤트 루프 실행
#
# @auth_bp.route("/signup", methods=["POST"])
# def signup():
#     data = request.get_json()
#
#     # 필수 필드 확인
#     required_fields = ["username", "email", "password", "cfpassword", "tweetId"]
#     if not all(field in data for field in required_fields):
#         return jsonify({"error": "Missing required fields"}), 400
#
#     username = data["username"]
#     email = data["email"]
#     password = data["password"]
#     cfpassword = data["cfpassword"]
#     tweet_id = data["tweetId"]
#
#     # 비밀번호 일치 여부 확인
#     if password != cfpassword:
#         return jsonify({"error": "Passwords do not match"}), 400
#
#     # 이메일 중복 확인
#     if User.query.filter_by(email=email).first():
#         return jsonify({"error": "User already exists"}), 409
#
#     # 비밀번호 해싱 후 저장
#     hashed_password = generate_password_hash(password)
#     new_user = User(username=username, email=email, password=hashed_password, tweet_id=tweet_id)
#
#     # DB에 등록
#     db.session.add(new_user)
#     db.session.commit()
#
#     # 트위터 ID로 유저 정보 가져오기
#     tweet_internal_id = fetch_twitter_id(tweet_id)
#     print(tweet_internal_id)
#
#     # 만약 트위터 ID가 없으면 오류 메시지 반환
#     if tweet_internal_id is None:
#         return jsonify({"error": "존재하지 않는 유저입니다"}), 404
#
#     # TweetUser 생성 및 연결
#     new_tweet_user = TweetUser(
#         tweet_internal_id=tweet_internal_id,
#         tweet_id=tweet_id,
#         user_id=new_user.id,  # 유저 ID와 트윗 유저를 연결
#     )
#
#     # Add TweetUser to the session
#     db.session.add(new_tweet_user)
#
#     try:
#         # Commit both User and TweetUser objects to the database
#         db.session.commit()
#         return jsonify({"message": "회원가입 성공"}), 201
#     except Exception as e:
#         # Rollback if there was an error
#         db.session.rollback()
#         return jsonify({"error": f"An error occurred: {str(e)}"}), 500
#
# @auth_bp.route("/login", methods=["POST"])
# def signin():
#     data = request.get_json()
#
#     if not data or "email" not in data or "password" not in data:
#         return jsonify({"error": "Missing email or password"}), 400
#
#     user = User.query.filter_by(email=data["email"]).first()
#
#     if user and check_password_hash(user.password, data["password"]):
#         access_token = create_access_token(identity=user.email)
#         return jsonify({"message": "로그인 성공", "token": access_token}), 200
#     else:
#         return jsonify({"error": "Invalid username or password"}), 401
#
# @auth_bp.route("/check_login", methods=["GET"])
# @jwt_required()
# def check_login():
#     current_user = get_jwt_identity()  # 현재 사용자 확인
#     return jsonify({"message": f"Logged in as {current_user}"}), 200
#
# @auth_bp.route("/logout", methods=["POST"])
# @jwt_required()
# def logout():
#     jti = get_jwt()["jti"]
#     print(f"Logging out user, JWT ID: {jti}")  # 디버깅용 출력
#     jwt_blocklist.add(jti)  # 블랙리스트에 추가
#     return jsonify({"message": "로그아웃 성공"}), 200