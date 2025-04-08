from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User

profile_bp = Blueprint('profile', __name__)


# Route to get user profile
@profile_bp.route('/api/profile/{tweet_id}', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()  # Get user id from JWT token
    user_profile = User.get_user_profile(user_id)

    if user_profile:
        return jsonify(user_profile), 200
    else:
        return jsonify({"error": "User not found"}), 404