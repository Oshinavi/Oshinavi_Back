from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from services.auth_service import signup_user, login_user, logout_user
from jwt_blocklist import jwt_blocklist

auth_bp = Blueprint("auth", __name__)

# 회원가입
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    return signup_user(data)

# 로그인
@auth_bp.route("/login", methods=["POST"])
def signin():
    data = request.get_json()
    return login_user(data)

# 로그아웃
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    jwt_blocklist.add(jti)
    return logout_user()

# 로그인 여부 체크
@auth_bp.route("/check_login", methods=["GET"])
@jwt_required()
def check_login():
    current_user = get_jwt_identity()
    return jsonify({"message": f"Logged in as {current_user}"}), 200