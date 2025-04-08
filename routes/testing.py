from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

# 예시로 모델을 작성한 후, 데이터베이스 연결 확인을 위한 쿼리를 실행할 수 있습니다.
@app.route('/check_db')
def check_db():
    try:
        # 데이터베이스에서 첫 번째 사용자 데이터를 가져와봄
        user = db.session.execute('SELECT 1').fetchone()
        return f"DB 연결 성공: {user}", 200
    except Exception as e:
        return f"DB 연결 실패: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)