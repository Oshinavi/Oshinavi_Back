import os
from dotenv import load_dotenv
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# ─── 0) settings.env 명시적 로드 ──────────────────────────────────
dotenv_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config", "settings.env")
)
if not os.path.exists(dotenv_path):
    raise RuntimeError(f"settings.env 파일을 찾을 수 없습니다: {dotenv_path}")
load_dotenv(dotenv_path, override=True)

# ─── app/core/config.py 의 pydantic Settings 에서 DATABASE_URL 등 읽어오기
from app.core.config import settings

# ─── 1) 데이터베이스 URL 결정 ─────────────────────────────────────
# 우선 settings.DATABASE_URL (async 스킴) 사용
db_async_url = settings.DATABASE_URL
if not db_async_url:
    # 없으면 개별 환경변수로 조합
    db_user = os.getenv("DB_USER", "translator")
    db_pw   = os.getenv("DB_PASSWORD", "translator_pw")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")       # 반드시 숫자 문자열
    db_name = os.getenv("DB_NAME", "x_translator")
    db_async_url = f"mysql+asyncmy://{db_user}:{db_pw}@{db_host}:{db_port}/{db_name}"

# 동기 마이그레이션용 URL (pymysql 스킴)
if db_async_url.startswith("mysql+asyncmy://"):
    db_sync_url = db_async_url.replace("mysql+asyncmy://", "mysql+pymysql://")
else:
    db_sync_url = db_async_url  # 만약 이미 pymysql 스킴이라면 그대로

# ─── 2) 비동기 엔진 생성 ───────────────────────────────────────
#    반드시 async 스킴인 db_async_url 을 넘겨야 에러가 없습니다.
async_engine = create_async_engine(
    db_async_url,
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

# ─── 3) 비동기 세션 팩토리 생성 ─────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─── 4) ORM 베이스 클래스 정의 ────────────────────────────────────────
Base = declarative_base()

# ─── 5) 테이블 생성 (앱 시작 시 1회) ──────────────────────────
async def init_db() -> None:
    """
    애플리케이션 시작 시 데이터베이스 테이블을 자동 생성
    """
    # 메타데이터에 포함된 모든 모델 import
    import app.models.user
    import app.models.twitter_user
    import app.models.post
    import app.models.reply_log
    import app.models.tweet_likes
    import app.models.user_oshi
    import app.models.schedule

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ─── 6) FastAPI 의존성 ───────────────────────────────────────
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 종속성: 요청마다 세션을 생성/종료
    """
    async with async_session_factory() as session:
        yield session