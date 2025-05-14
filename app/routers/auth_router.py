from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

from app.schemas.auth_schema import SignupRequest, LoginRequest, TokenResponse, MessageResponse
from app.services.auth_service import AuthService
from app.core.database import get_db_session
from app.dependencies import get_current_user_optional, get_current_user
from app.utils.exceptions import UnauthorizedError
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

COOKIE_PATH = "/"  # 쿠키 경로 통일
COOKIE_SAMESITE = "none"  # cross-site 전송 허용
COOKIE_SECURE = True  # 개발 환경: HTTP 허용 (배포 시 True 로 변경)
COOKIE_HTTPONLY = True
COOKIE_MAX_AGE = 60 * 60 * 24 * settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    req: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    회원가입 및 자동 로그인 처리.
    access_token 은 jwt_token 쿠키로, refresh_token 은 refresh_token 쿠키로 저장합니다.
    """
    tokens = await AuthService(db).signup(req)

    # access_token → jwt_token 쿠키
    response.set_cookie(
        key="jwt_token",
        value=tokens["access_token"],
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=60 * settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES,
        path=COOKIE_PATH,
    )
    # refresh_token → refresh_token 쿠키
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
        path=COOKIE_PATH,
    )

    return {
        "message":       "회원가입 및 로그인 성공",
        "access_token":  tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type":    "bearer",
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    로그인 처리.
    access_token 은 jwt_token 쿠키로, refresh_token 은 refresh_token 쿠키로 저장합니다.
    """
    try:
        tokens = await AuthService(db).login(req.email, req.password)

        # access_token → jwt_token 쿠키
        response.set_cookie(
            key="jwt_token",
            value=tokens["access_token"],
            httponly=COOKIE_HTTPONLY,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=60 * settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES,
            path=COOKIE_PATH,
        )
        # refresh_token → refresh_token 쿠키
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh_token"],
            httponly=COOKIE_HTTPONLY,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=COOKIE_MAX_AGE,
            path=COOKIE_PATH,
        )

        return {
            "message":       "로그인 성공",
            "access_token":  tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type":    "bearer",
        }

    except UnauthorizedError:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request):
    """
    쿠키에 저장된 refresh_token 으로 액세스 토큰만 재발급합니다.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다")

    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="리프레시 토큰이 아닙니다")

        now = datetime.now(timezone.utc)
        access_exp = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES)
        new_payload = {
            "sub": payload["sub"],
            "exp": access_exp,
            "jti": payload["jti"],
            "type": "access"
        }
        access_token = jwt.encode(new_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

        return {
            "message":       "액세스 토큰 재발급 성공",
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "token_type":    "bearer",
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 유효하지 않습니다")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    # 현재 사용자 인증이 실패해도 None 을 리턴하도록 변경
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
):
    """
    로그아웃 처리.
    Authorization 헤더에 담긴 access_token 을 블록리스트에 등록하고,
    쿠키를 모두 삭제합니다.
    """
    auth: str | None = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token_str = auth.split(" ", 1)[1]
        try:
            AuthService(db).logout(token_str)
        except Exception:
            # 이미 만료된 토큰이라도 무시
            pass

    # 쿠키 삭제
    response.delete_cookie("refresh_token", path=COOKIE_PATH)
    response.delete_cookie("jwt_token", path=COOKIE_PATH)
    return {"message": "로그아웃 성공"}


@router.get("/check_login", response_model=MessageResponse)
async def check_login(current_user=Depends(get_current_user)):
    """
    로그인 상태 확인용 엔드포인트.
    """
    return {"message": f"Logged in as {current_user.email}"}