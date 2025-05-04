from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from services.auth_service import AuthService
from services.exceptions import ApiError

auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()

# 회원가입
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    try:
        auth_service.signup(
            username=data.get("username", ""),
            email=data.get("email", ""),
            password=data.get("password", ""),
            cfpassword=data.get("cfpassword", ""),
            tweet_id=data.get("tweet_id", "")
        )
        return jsonify({"message": "회원가입에 성공했습니다."}), 201

    # 에러 반환
    except ApiError as e:
        return e.to_response()

    # Unexpected error 처리
    except Exception as e:
        return jsonify({"error": "서버 에러가 발생했습니다."}), 500


# 로그인
@auth_bp.route("/login", methods=["POST"])
def signin():
    data = request.get_json() or {}
    try:
        token = auth_service.login(
            email=data.get("email", ""),
            password=data.get("password", "")
        )
        return jsonify({"message":"로그인에 성공했습니다.", "token": token}), 200

    # 에러 반환
    except ApiError as e:
        return e.to_response()

    # Unexpected error 처리
    except Exception as e:
        return jsonify({"error": "서버 에러가 발생했습니다."}), 500


# 로그아웃
@auth_bp.route("/logout", methods=["POST"])
def logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(None, 1)[1].strip()
        try:
            decoded = decode_token(token)          # 공개 API 사용
            jti = decoded.get("jti")
            if jti:
                from jwt_blocklist import jwt_blocklist
                jwt_blocklist.add(jti)
        except Exception:
            # 만료되었거나 포맷 오류일 때 무시
            pass

    # 항상 성공 응답
    return jsonify({"message": "로그아웃 성공"}), 200

# 로그인 여부 체크
@auth_bp.route("/check_login", methods=["GET"])
@jwt_required()
def check_login():
    user = get_jwt_identity()
    return jsonify({"message": f"Logged in as {user}"}), 200

