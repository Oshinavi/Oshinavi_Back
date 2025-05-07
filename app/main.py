# app/main.py
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError

# 라우터 가져오기…
from app.routers.auth_router     import router as auth_router
from app.routers.user_router     import router as user_router
from app.routers.tweet_router    import router as tweet_router
from app.routers.schedule_router import router as schedule_router
from app.routers.protected       import router as protected_router

# 예외 정의…
from app.utils.exceptions import BadRequestError, ConflictError, NotFoundError, UnauthorizedError

# 방금 추가한 init_db 가져오기
from app.core.database import init_db

app = FastAPI(
    title="X_Translator API",
    description="일본어 트윗 기반 스케줄 추출 및 트위터 연동 기능 제공",
    version="1.0.0",
)

# CORS 설정…
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# **charset 강제 미들웨어
@app.middleware("http")
async def ensure_utf8(request: Request, call_next):
    resp = await call_next(request)

    # ① media_type 가 None 이면 건드리지 않음
    if resp.media_type and resp.media_type.startswith("application/json"):

        # ② 이미 charset 파라미터가 있으면 두지 않음
        ctype = resp.headers.get("Content-Type", "")
        if "charset" not in ctype.lower():
            resp.headers["Content-Type"] = "application/json; charset=utf-8"

    return resp

# 커스텀 예외 핸들러…
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
    print("⚠️ RAW BODY:", await request.body())
    return ORJSONResponse(status_code=422, content={"detail": exc.errors()})

# **이 부분이 핵심**: 서버가 올라갈 때 DB 테이블을 모두 생성
@app.on_event("startup")
async def on_startup():
    await init_db()

# 라우터 등록
app.include_router(auth_router,      prefix="/api", tags=["Auth"])
app.include_router(protected_router, prefix="/api",      tags=["Protected"])
app.include_router(user_router,      prefix="/api",      tags=["User"])
app.include_router(tweet_router,     prefix="/api",      tags=["Tweet"])
app.include_router(schedule_router,  prefix="/api",      tags=["Schedule"])

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)