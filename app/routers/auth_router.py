from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone

from app.schemas.auth_schema import (
    SignupRequest, LoginRequest, TokenResponse, MessageResponse
)
from app.services.auth_service import AuthService
from app.core.database import get_db_session
from app.dependencies import get_current_user_optional, get_current_user
from app.utils.exceptions import UnauthorizedError
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

# 쿠키 설정 상수
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
ACCESS_TOKEN_COOKIE_NAME = "jwt_token"
COOKIE_PATH = "/"  # 쿠키 경로 통일
COOKIE_SAMESITE = "none"  # cross-site 전송 허용
COOKIE_SECURE = True  # 개발 환경: HTTP 허용 (배포 시 True 로 변경)
COOKIE_HTTPONLY = True
COOKIE_REFRESH_MAX_AGE = 60 * 60 * 24 * settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS
COOKIE_ACCESS_MAX_AGE = 60 * settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES

def _set_auth_cookies(
        response: Response,
        access_token: str,
        refresh_token: str
) -> None:
    """
    응답 객체에 인증용 쿠키(access, refresh) 설정 추가
    """
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_ACCESS_MAX_AGE,
        path=COOKIE_PATH,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_REFRESH_MAX_AGE,
        path=COOKIE_PATH,
    )


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED
)

async def signup(
    req: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    회원가입 및 로그인 처리 후 토큰을 쿠키에 저장
    """
    tokens = await AuthService(db, settings.USER_INTERNAL_ID).signup(req)
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return {
        "message": "회원가입 및 로그인 성공",
        **tokens,
    }

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    로그인 처리 및 토큰을 쿠키에 저장
    """
    try:
        tokens = await AuthService(db).login(req.email, req.password)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return {
        "message": "로그인 성공",
        **tokens,
    }

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
) -> dict:
    """
    리프레시 토큰으로 액세스 토큰 재발급
    """
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 없습니다"
        )

    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
        if payload.get("type") != "refresh":
            raise JWTError("Not a refresh token")
        # 새로운 액세스 토큰 생성
        now = datetime.now(timezone.utc)
        access_payload = {
            "sub": payload["sub"],
            "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES),
            "jti": payload["jti"],
            "type": "access",
        }
        new_access_token = jwt.encode(
            access_payload,
            settings.JWT_SECRET_KEY,
            algorithm="HS256"
        )
        # 쿠키 갱신
        response.set_cookie(
            key=ACCESS_TOKEN_COOKIE_NAME,
            value=new_access_token,
            httponly=COOKIE_HTTPONLY,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=COOKIE_ACCESS_MAX_AGE,
            path=COOKIE_PATH,
        )
        return {
            "message": "액세스 토큰 재발급 성공",
            "access_token": new_access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 유효하지 않습니다"
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    로그아웃 처리
    - access_token 블랙리스트 등록
    - 인증 쿠키 삭제
    """
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            AuthService(db, settings.USER_INTERNAL_ID).logout(token)
        except Exception:
            pass

    # 쿠키 삭제
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, path=COOKIE_PATH)
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path=COOKIE_PATH)
    return {"message": "로그아웃 성공"}

@router.get("/check_login", response_model=MessageResponse)
async def check_login(current_user=Depends(get_current_user)) -> dict:
    """
    로그인 상태 확인용 엔드포인트
    """
    return {"message": f"Logged in as {current_user.email}"}