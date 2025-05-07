# app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(..., description="OpenAI API 키")            # ← 추가
    SECRET_KEY: str       = Field(..., description="FastAPI 세션용 비밀키")
    JWT_SECRET_KEY: str   = Field(..., description="JWT 서명용 비밀키")

    DB_USER:     str
    DB_PASSWORD: str
    DB_HOST:     str
    DB_PORT:     int
    DB_NAME:     str

    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRES_DAYS:    int = 7

    class Config:
        # 실제 파일명이 settings.env 라면 여기를 맞춰 주세요
        env_file = str(
            Path(__file__).resolve()
                .parent.parent  # -> app/
                .joinpath("config", "settings.env")
        )
        env_file_encoding = "utf-8"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()