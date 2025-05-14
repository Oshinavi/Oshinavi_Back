from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from pathlib import Path
from functools import lru_cache
from typing import Optional

# 프로젝트 기반 디렉토리 경로
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    애플리케이션 설정 모델
    - .env 파일 및 환경 변수를 통해 설정값 로드
    - 데이터베이스 URL 자동 구성 및 파일 경로 해석 기능 포함
    """
    # Pydantic 설정: .env 파일 경로 및 추가 필드 무시
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "config" / "settings.env"),
        env_file_encoding="utf-8",
        extra='ignore',
    )

    # ── Security & JWT ─────────────────────────────────────────
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = Field(
        60,
        env="JWT_ACCESS_TOKEN_EXPIRES_MINUTES",
        description="액세스 토큰 만료 시간(분)",
    )
    JWT_REFRESH_TOKEN_EXPIRES_DAYS: int = Field(
        7,
        env="JWT_REFRESH_TOKEN_EXPIRES_DAYS",
        description="리프레시 토큰 만료 시간(일)",
    )

    # ── Database ───────────────────────────────────────────────
    DB_USER:     str
    DB_PASSWORD: str
    DB_HOST:     str
    DB_PORT:     int
    DB_NAME:     str

    # .env 에 DATABASE_URL 이 있으면 그걸 쓰고, 없으면 아래 validator 가 합성
    DATABASE_URL: Optional[str] = Field(
        None,
        description="전체 DB 연결 URL (우선순위: env > 자동 조합)",
    )

    # ── OpenAI ─────────────────────────────────────────────────
    OPENAI_API_KEY: str

    # ── RAG / FAISS ────────────────────────────────────────────
    FAISS_INDEX_PATH: str = Field(
        default=str(BASE_DIR / "rag_data" / "vector_store" / "faiss_index.bin"),
        description="FAISS 벡터 인덱스 파일 경로",
    )
    FAISS_META_PATH: str  = Field(
        default=str(BASE_DIR / "rag_data" / "vector_store" / "metadata.json"),
        description="FAISS 메타데이터 파일 경로",
    )
    RAG_TOP_K: int = Field(
        10,
        description="RAG 질의 시 상위 K개 문서 선택",
    )

    # ── Legacy Settings ─────────────────────────────────────────
    # 이전 버전 호환을 위한 필드
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
    """
    Settings 인스턴스를 싱글톤으로 반환
    - 최초 호출시에만 Settings를 생성 및 캐싱
    """
    return Settings()

# 전역 설정 인스턴스
settings = get_settings()