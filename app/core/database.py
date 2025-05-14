from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# ─── 1) 비동기 엔진 생성 ───────────────────────────────────────
#    - settings.DATABASE_URL에는 utf8mb4 문자셋 포함
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={
        # MySQL 연결 시 UTF-8 charset 설정
        "charset": "utf8mb4",
        "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
        "autocommit": True,
    },
    pool_recycle=1800,  # 커넥션 풀에서 오래된 커넥션 재활용 주기(초)
    pool_pre_ping=True, # 사용 전 커넥션 유효성 체크
)

# ─── 2) 비동기 세션 팩토리 생성 ─────────────────────────────────────────
#    - expire_on_commit=False로 커밋 후에도 객체 유지
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─── 3) ORM 베이스 클래스 정의 ────────────────────────────────────────
Base = declarative_base()

# ─── 4) 테이블 생성 (앱 시작 시 1회) ──────────────────────────
async def init_db() -> None:
    """
    애플리케이션 시작 시 데이터베이스 테이블을 자동 생성
    - 메타데이터에 등록된 모든 모델을 기반으로 테이블 생성
    """
    # 모델 import(메타데이터 등록)
    import app.models.user          # noqa
    import app.models.twitter_user  # noqa
    import app.models.post          # noqa
    import app.models.reply_log     # noqa
    import app.models.tweet_likes   # noqa
    import app.models.user_oshi     # noqa
    import app.models.schedule      # noqa

    # 비동기 트랜잭션 컨텍스트에서 테이블 생성 실행
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ─── 5) FastAPI 의존성 ───────────────────────────────────────
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 종속성으로 사용되는 DB 세션 제공자
    - 요청 처리 시 세션을 생성, 완료 후 자동으로 close
    """
    async with async_session_factory() as session:
        yield session
