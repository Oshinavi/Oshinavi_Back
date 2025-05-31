import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv


# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# 환경 변수 로딩
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.env')


def load_environment(env_path: str = ENV_PATH) -> None:
    """
    .env 파일을 읽어 환경 변수를 설정
    """
    load_dotenv(env_path, override=True)



def build_database_url() -> str:
    """
    DATABASE_URL 환경 변수를 우선 사용하고, 없으면 개별 변수로 MySQL URL을 생성
    asyncmy URL은 pymysql로 교체하여 동기 커넥터로 사용
    """
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return _convert_async_to_sync(db_url)

    user = os.environ['DB_USER']
    pw = os.environ['DB_PASSWORD']
    host = os.environ['DB_HOST']
    port = os.environ['DB_PORT']
    name = os.environ['DB_NAME']
    async_url = f"mysql+asyncmy://{user}:{pw}@{host}:{port}/{name}"
    return _convert_async_to_sync(async_url)


def _convert_async_to_sync(url: str) -> str:
    """
    asyncmy 접두어를 pymysql로 변경하여 동기 커넥터 URL로 변환
    """
    async_prefix = 'mysql+asyncmy://'
    sync_prefix = 'mysql+pymysql://'
    if url.startswith(async_prefix):
        return url.replace(async_prefix, sync_prefix, 1)
    return url


# .env 로드
load_environment()

# 알렘빅 설정 객체 가져오기
alembic_cfg = context.config
if alembic_cfg.config_file_name:
    fileConfig(alembic_cfg.config_file_name)

# SQLAlchemy URL 설정
database_url = build_database_url()
alembic_cfg.set_main_option('sqlalchemy.url', database_url)

# 메타데이터 바인딩
from app.core.database import Base  # noqa: E402
import app.models.twitter_user  # noqa: E402
import app.models.post          # noqa: E402
import app.models.user          # noqa: E402
import app.models.user_oshi     # noqa: E402
import app.models.schedule      # noqa: E402
import app.models.reply_log     # noqa: E402
import app.models.tweet_likes   # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    오프라인 모드에서 SQL 스크립트를 생성
    """
    url = alembic_cfg.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    온라인 모드에서 데이터베이스에 직접 연결하여 마이그레이션을 실행
    """
    connectable = engine_from_config(
        alembic_cfg.get_section(alembic_cfg.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# 엔트리포인트
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()