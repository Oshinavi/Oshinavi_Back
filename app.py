from flask_jwt_extended import JWTManager
from Controller.tweet_controller import tweet_bp
from db import create_app
from routes.auth_controller import auth_bp
from routes.protected import protected_bp
from jwt_blocklist import jwt_blocklist  # 블랙리스트 가져오기
from routes.user import user_bp

app = create_app()
jwt = JWTManager(app)


# 블랙리스트된 토큰 차단 설정
@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    return jwt_payload["jti"] in jwt_blocklist  # 블랙리스트를 전역적으로 참조

# 블루프린트 등록
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(protected_bp, url_prefix='/api')
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(tweet_bp, url_prefix='/api')


if __name__ == "__main__":
    print("🚀 Starting Flask server...")  # ← 디버깅 로그
    app.run(debug=True, use_reloader=False)