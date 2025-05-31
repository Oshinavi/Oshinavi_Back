from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from pathlib import Path
from functools import lru_cache
from typing import Optional

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent

def _resolve_path(path_str: str) -> str:
    """
    입력된 경로가 절대 경로인지 확인하고 상대 경로일 경우 BASE_DIR 기준으로 변환
    """
    path = Path(path_str)
    return str(path if path.is_absolute() else BASE_DIR / path)

class Settings(BaseSettings):
    """
    애플리케이션 환경 설정 모델
    - .env 파일을 자동 로드
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / "config" / "settings.env"),
        env_file_encoding="utf-8",
        extra='ignore',
    )

    # Security & JWT
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

    # Database
    DB_USER:     str
    DB_PASSWORD: str
    DB_HOST:     str
    DB_PORT:     int
    DB_NAME:     str
    DATABASE_URL: Optional[str] = Field(
        None,
        description="전체 DB 연결 URL (우선순위: env > 자동 조합)",
    )

    # OpenAI & Anthropic
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str

    # RAG / FAISS
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

    # Legacy Settings
    ollama_api_url: Optional[str]
    ollama_model:   Optional[str]

    @validator("FAISS_INDEX_PATH", "FAISS_META_PATH", pre=True)
    def _validate_paths(cls, v: str) -> str:
        """
        파일 경로 필드가 절대 경로가 아닐 경우 BASE_DIR 기준으로 변환
        """
        return _resolve_path(v)

    @validator("DATABASE_URL", pre=True, always=True)
    def _assemble_database_url(cls, v: Optional[str], values) -> str:
        """
        DATABASE_URL이 설정되어 있으면 그대로 사용하고, 없으면 개별 DB 설정값으로 URL을 조합
        """
        if v:
            return v
        user = values.get("DB_USER")
        pw   = values.get("DB_PASSWORD")
        host = values.get("DB_HOST")
        port = values.get("DB_PORT")
        name = values.get("DB_NAME")
        return f"mysql+asyncmy://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        SQLAlchemy가 기대하는 이름의 DB 연결 문자열을 반환
        """
        return self.DATABASE_URL  # 항상 존재함

@lru_cache()
def get_settings() -> Settings:
    """
    Settings 인스턴스를 싱글톤으로 반환
    최초 호출 시 객체를 생성하고, 이후 캐싱된 인스턴스를 반환
    """
    return Settings()

# 전역 설정 인스턴스
settings = get_settings()