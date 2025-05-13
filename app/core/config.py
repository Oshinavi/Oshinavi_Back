from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from pathlib import Path
from functools import lru_cache
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "config" / "settings.env"),
        env_file_encoding="utf-8",
        extra='ignore'
    )

    # ── Security & JWT ─────────────────────────────────────────
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = Field(60, env="JWT_ACCESS_TOKEN_EXPIRES_MINUTES")
    JWT_REFRESH_TOKEN_EXPIRES_DAYS:    int = Field(7,  env="JWT_REFRESH_TOKEN_EXPIRES_DAYS")

    # ── Database ───────────────────────────────────────────────
    DB_USER:     str
    DB_PASSWORD: str
    DB_HOST:     str
    DB_PORT:     int
    DB_NAME:     str

    # .env 에 DATABASE_URL 이 있으면 그걸 쓰고, 없으면 아래 validator 가 합성합니다.
    DATABASE_URL: Optional[str] = Field(
        None,
        description="SQLAlchemy 연결 URL (우선순위: env의 DATABASE_URL > DB_USER 등 자동 생성)"
    )

    # ── OpenAI ─────────────────────────────────────────────────
    OPENAI_API_KEY: str

    # ── RAG / FAISS ────────────────────────────────────────────
    FAISS_INDEX_PATH: str = Field(
        default=str(BASE_DIR / "rag_data" / "vector_store" / "faiss_index.bin"),
    )
    FAISS_META_PATH: str  = Field(
        default=str(BASE_DIR / "rag_data" / "vector_store" / "metadata.json"),
    )
    RAG_TOP_K: int        = Field(10)

    # (이전 버전에서 사용하던 필드; .env 에 남아있어도 무시)
    ollama_api_url: Optional[str]
    ollama_model:   Optional[str]

    @validator("FAISS_INDEX_PATH", "FAISS_META_PATH", pre=True)
    def _resolve_relative_paths(cls, v: str) -> str:
        p = Path(v)
        if not p.is_absolute():
            p = BASE_DIR / p
        return str(p)

    @validator("DATABASE_URL", pre=True, always=True)
    def _assemble_db_url(cls, v, values):
        if v:
            return v
        user = values.get("DB_USER")
        pw   = values.get("DB_PASSWORD")
        host = values.get("DB_HOST")
        port = values.get("DB_PORT")
        name = values.get("DB_NAME")
        return (
            f"mysql+asyncmy://{user}:{pw}@{host}:{port}/{name}"
            "?charset=utf8mb4"
        )

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # SQLAlchemy 가 기대하는 이름
        return self.DATABASE_URL  # 위 validator 로 항상 값이 채워짐

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# 전역 설정 인스턴스
settings = get_settings()