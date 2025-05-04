from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from jwt_blocklist import jwt_blocklist

protected_bp = Blueprint("protected", __name__)

@protected_bp.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    jti = get_jwt()["jti"]  # Get the unique JWT identifier

    if jti in jwt_blocklist:
        return jsonify({"error": "토큰이 무효화되었습니다."}), 401

    return jsonify({"message": f"Hello, {current_user}! This is a protected route."})