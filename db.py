from flask import Flask
from flask_migrate import Migrate
from models import db
from config import Config

# DB 초기화

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # Migrate 객체 초기화
    migrate = Migrate(app, db)

    return app