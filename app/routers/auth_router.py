# app/routers/auth_router.py
import logging
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
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.utils.exceptions import UnauthorizedError
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# 쿠키 설정 상수
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
ACCESS_TOKEN_COOKIE_NAME  = "jwt_token"
COOKIE_PATH               = "/"
COOKIE_SAMESITE           = "none"
COOKIE_SECURE             = True
COOKIE_HTTPONLY           = True
COOKIE_REFRESH_MAX_AGE    = 60 * 60 * 24 * settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS
COOKIE_ACCESS_MAX_AGE     = 60 * settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
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
    1) Master 쿠키로 로그인
    2) TwitterUserService.get_user_info(screen_name) 호출 → internal ID 조회
    3) per-user 클라이언트 생성 → per-user 쿠키 저장
    4) AuthService.signup 호출 → JWT 쿠키 설정
    """
    # 1) master client 로 로그인
    master_client = TwitterClientService(user_internal_id="master")
    master_client.set_initial_cookies(req.ct0, req.auth_token)
    try:
        await master_client.ensure_login()
        logger.info("1) Master 로그인 성공")
    except Exception as e:
        logger.error(f"마스터 계정 로그인 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="트위터 인증정보가 유효하지 않습니다."
        )

    # 2) screen_name → internal ID 조회
    twitter_svc_master = TwitterUserService(client_service=master_client)
    try:
        info = await twitter_svc_master.get_user_info(req.tweet_id)
        new_internal_id = str(info["id"])
        logger.info(f"새 내부 id: {new_internal_id}")
    except Exception as e:
        logger.error(f"Internal ID 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="트위터 사용자 정보를 불러올 수 없습니다."
        )

    # 3) per-user client/service 생성 및 쿠키 저장
    user_client = TwitterClientService(user_internal_id=new_internal_id)
    user_client.set_initial_cookies(req.ct0, req.auth_token)
    try:
        await user_client.ensure_login()
        user_client.save_cookies_to_file()
        logger.info("3) Per-user 쿠키 저장 성공")
    except Exception as e:
        logger.warning(f"Per-user 쿠키 저장 실패: {e}")

    # 4) AuthService.signup 호출 및 JWT 쿠키 설정
    twitter_svc_user = TwitterUserService(client_service=user_client)
    tokens = await AuthService(db, twitter_svc_user).signup(req)
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    logger.info("4) AuthService.signup 성공")
    return {"message": "회원가입 및 로그인 성공", **tokens}

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    로그인 처리 및 JWT 쿠키 저장
    """
    try:
        tokens = await AuthService(db).login(req.email, req.password)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    _set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return {"message": "로그인 성공", **tokens}

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
        _set_auth_cookies(response, new_access_token, refresh_token)
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
    로그아웃 처리 (블랙리스트 + 쿠키 삭제)
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            AuthService(db).logout(token)
        except Exception:
            pass
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, path=COOKIE_PATH)
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path=COOKIE_PATH)
    return {"message": "로그아웃 성공"}

@router.get("/check_login", response_model=MessageResponse)
async def check_login(current_user=Depends(get_current_user)) -> dict:
    """
    로그인 상태 확인
    """
    return {"message": f"Logged in as {current_user.email}"}