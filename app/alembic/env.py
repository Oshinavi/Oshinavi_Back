import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# ─── 프로젝트 루트를 PYTHONPATH에 추가 ──────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ─── .env 로드 ─────────────────────────────────────────
#    프로젝트 루트에 .env 파일이 있어야 합니다.
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'config', 'settings.env'))
load_dotenv(dotenv_path, override=True)

# ─── Alembic Config 객체 ───────────────────────────────
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# ─── 환경변수에서 DB 연결 정보 읽기 ─────────────────────
# 우선 DATABASE_URL 환경변수 사용, 없으면 개별 변수로 조합
database_url = os.getenv("DATABASE_URL")
if not database_url:
    user = os.environ["DB_USER"]
    pw   = os.environ["DB_PASSWORD"]
    host = os.environ["DB_HOST"]
    port = os.environ["DB_PORT"]
    name = os.environ["DB_NAME"]
    # async URL
    database_url = f"mysql+asyncmy://{user}:{pw}@{host}:{port}/{name}"

# 동기 커넥터가 필요하면 `mysql+pymysql://` 스킴으로 치환
if database_url.startswith("mysql+asyncmy://"):
    database_url = database_url.replace("mysql+asyncmy://", "mysql+pymysql://")

# 최종 URL을 alembic 설정에 반영
config.set_main_option("sqlalchemy.url", database_url)

# ─── 메타데이터 바인딩 ─────────────────────────────────
from app.core.database import Base  # 프로젝트 구조에 맞게 조정
target_metadata = Base.metadata

# ─── 마이그레이션 함수 ─────────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

# ─── entrypoint ────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()