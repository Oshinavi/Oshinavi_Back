import os
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.database import init_db
from app.rag_data.build_faiss import build as build_faiss
from app.routers.auth_router import router as auth_router
from app.routers.protected import router as protected_router
from app.routers.user_router import router as user_router
from app.routers.tweet_router import router as tweet_router
from app.routers.schedule_router import router as schedule_router
from app.utils.exceptions import BadRequestError, ConflictError, NotFoundError, UnauthorizedError

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
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("tokenizers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

# ─── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 프론트엔드 주소
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.middleware("http")
async def ensure_utf8(request: Request, call_next):
    resp = await call_next(request)
    if resp.media_type and resp.media_type.startswith("application/json"):
        ctype = resp.headers.get("Content-Type", "")
        if "charset" not in ctype.lower():
            resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

# ─── 예외 처리 ─────────────────────────────────────────────────────────
@app.exception_handler(BadRequestError)
async def bad_request_handler(request: Request, exc: BadRequestError):
    return ORJSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return ORJSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return ORJSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return ORJSONResponse(status_code=401, content={"detail": str(exc)})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    logging.warning(f"⚠️ RAW BODY: {body!r}")
    return ORJSONResponse(status_code=422, content={"detail": exc.errors()})

# ─── 앱 시작 시 DB · FAISS 초기화 ─────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    # 1) DB 테이블 자동 생성
    await init_db()

    # 2) FAISS 인덱스 빌드 (없으면)
    idx = Path(settings.FAISS_INDEX_PATH)
    meta = Path(settings.FAISS_META_PATH)
    if not idx.exists() or not meta.exists():
        build_faiss()

# ─── 라우터 등록 ───────────────────────────────────────────────────────
app.include_router(auth_router,      prefix="/api")
app.include_router(protected_router, prefix="/api")
app.include_router(user_router,      prefix="/api")
app.include_router(tweet_router,     prefix="/api")
app.include_router(schedule_router,  prefix="/api")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)