import os
from datetime import timedelta

# 설정 file
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:hk1237**@localhost:3306/media2025?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = "TWVkaWFQcm9qZWN0MjAyNV9qd3Rfc2VjcmV0X2tleV9lbmNvZGVk"

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)