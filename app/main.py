import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Type

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.rag_data.build_faiss import build_faiss_index as build_faiss
from app.routers.auth_router import router as auth_router
from app.routers.protected import router as protected_router
from app.routers.user_router import router as user_router
from app.routers.tweet_router import router as tweet_router
from app.routers.schedule_router import router as schedule_router
from app.utils.exceptions import (
    BadRequestError, ConflictError,
    NotFoundError, UnauthorizedError
)

# logging.basicConfig(level=logging.DEBUG)

# ─── 애플리케이션 수명 주기 이벤트 핸들러 정의 ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 시작 시 DB 초기화 및 FAISS 인덱스 빌드 수행
    """
    # DB 테이블 자동 생성
    await init_db()

    # FAISS 인덱스 및 메타 파일 경로
    faiss_index_path = Path(settings.FAISS_INDEX_PATH)
    faiss_meta_path = Path(settings.FAISS_META_PATH)
    # 인덱스가 없으면 빌드
    if not faiss_index_path.exists() or not faiss_meta_path.exists():
        build_faiss()

    yield

# ─── FastAPI 애플리케이션 인스턴스 생성 ─────────────────────────────────────
app = FastAPI(
    title="X_Translator API",
    description="일본어 트윗 기반 스케줄 추출 및 트위터 연동 기능 제공",
    version="1.0.0",
)

# ─── 로그 설정 ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# transformers/tokenizers 라이브러리의 과도한 로그 억제
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("tokenizers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

# ─── CORS 설정 ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 프론트엔드 도메인 설정값 사용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 예외 클래스 → Status Code 매핑 ───────────────────────────────────────
EXCEPTION_STATUS_MAP: dict[Type[Exception], int] = {
    BadRequestError: 400,
    ConflictError: 409,
    NotFoundError: 404,
    UnauthorizedError: 401,
}

@app.get("/health")
async def health_check() -> dict:
    """
    서비스 상태 확인용 테스트 엔드포인트
    """
    return {"status": "ok"}

@app.middleware("http")
async def ensure_utf8(request: Request, call_next):
    """
    모든 JSON 응답에 UTF-8 charset을 명시적으로 추가
    """
    resp = await call_next(request)
    if resp.media_type and resp.media_type.startswith("application/json"):
        ctype = resp.headers.get("Content-Type", "")
        if "charset" not in ctype.lower():
            resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

# ─── 예외 처리 핸들러 등록───────────────────────────────────────────────────
async def handle_api_error(request: Request, exc: Exception):
    """
    커스텀 ApiError를 비롯한 예외를 일괄 처리
    EXCEPTION_STATUS_MAP에 매핑된 예외라면 해당 상태 코드로, 그렇지 않으면 500 Internal Server Error로 반환
    """
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    detail = str(exc) if hasattr(exc, "message") else repr(exc)
    return ORJSONResponse(status_code=status_code, content={"detail": detail})

# ─── 라우터 등록 ───────────────────────────────────────────────────────
app.include_router(auth_router,      prefix="/api")
app.include_router(protected_router, prefix="/api")
app.include_router(user_router,      prefix="/api")
app.include_router(tweet_router,     prefix="/api")
app.include_router(schedule_router,  prefix="/api")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )