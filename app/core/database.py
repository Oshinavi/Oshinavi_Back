import os
from pathlib import Path
from dotenv import load_dotenv
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# .env 파일 로드
ENV_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.env"

def load_env(env_path: Path = ENV_PATH) -> None:
    """
    지정된 .env 파일을 로드하여 환경 변수를 설정
    """
    if not env_path.exists():
        raise RuntimeError(f"환경 설정 파일을 찾을 수 없습니다: {env_path}")
    load_dotenv(env_path, override=True)


def build_database_urls() -> tuple[str, str]:
    """
    설정된 settings.DATABASE_URL 또는 개별 환경 변수로부터
    비동기 및 동기 DB 연결 URL을 생성하여 반환
    """
    async_url = settings.DATABASE_URL or (
        f"mysql+asyncmy://{os.getenv('DB_USER','translator')}"
        f":{os.getenv('DB_PASSWORD','translator_pw')}@"
        f"{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','3306')}"
        f"/{os.getenv('DB_NAME','x_translator')}"
    )
    # 동기용 스킴 변환
    sync_url = (
        async_url.replace('mysql+asyncmy://', 'mysql+pymysql://', 1)
        if async_url.startswith('mysql+asyncmy://')
        else async_url
    )
    return async_url, sync_url


# 환경 로드
load_env()

# DB URL 설정
DB_ASYNC_URL, DB_SYNC_URL = build_database_urls()

# 비동기 엔진 및 세션 팩토리 생성
async_engine = create_async_engine(
    DB_ASYNC_URL,
    echo=False,
    future=True,
    connect_args={
        "charset": "utf8mb4",
        "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
        "autocommit": True,
    },
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ORM 베이스
Base = declarative_base()

async def init_db() -> None:
    """
    애플리케이션 시작 시 호출하여 메타데이터 기반 테이블을 생성
    """
    # 모델 import로 메타데이터 등록
    from app.models import (
        user, twitter_user, post,
        reply_log, tweet_likes, user_oshi, schedule
    )

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 종속성: 요청마다 새로운 DB 세션을 생성 후 반환
    """
    async with async_session_factory() as session:
        yield session
