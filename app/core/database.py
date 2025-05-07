# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# ─────────────────────────────────────────────────────────────
# 1) 비동기 엔진
engine = create_async_engine(
    f"mysql+asyncmy://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    "?charset=utf8mb4",
    echo=False,
    future=True,
    connect_args={
        "charset": "utf8mb4",
        "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
        "autocommit": True,  # 선택 – 긴 트랜잭션이 없으면 편함
    },
    pool_recycle=1800,   # 장시간 연결 유지 시 권장
    pool_pre_ping=True,  # 연결 끊김 자동 감지

)
# ─────────────────────────────────────────────────────────────

# 2) 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 3) 베이스 클래스
Base = declarative_base()

# 4) 테이블 생성 (앱 시작 시 1회)
async def init_db() -> None:
    # 모델 import(메타데이터 등록)
    import app.models.user           # noqa
    import app.models.twitter_user   # noqa
    import app.models.post           # noqa
    import app.models.reply_log      # noqa
    import app.models.tweet_likes    # noqa
    import app.models.user_oshi      # noqa
    import app.models.schedule       # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 5) FastAPI dependency
async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session