import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response, Request
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth_schema import SignupRequest, LoginRequest, TokenResponse, MessageResponse
from app.services.auth_service import AuthService
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.core.database import get_db_session
from app.dependencies import get_current_user
from app.core.config import settings
from app.utils.exceptions import BadRequestError, UnauthorizedError

# 로거 설정
logger = logging.getLogger(__name__)

# 쿠키 설정용 데이터 클래스
class CookieConfig:
    ACCESS_NAME = "jwt_token"
    REFRESH_NAME = "refresh_token"
    PATH = "/"
    SAMESITE = "none"
    SECURE = True
    HTTPONLY = True
    ACCESS_MAX_AGE = 60 * settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES
    REFRESH_MAX_AGE = 60 * 60 * 24 * settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS

    @classmethod
    def set_cookies(cls, response: Response, access: str, refresh: str) -> None:
        """
        응답에 액세스 및 리프레시 토큰 쿠키를 설정
        """
        for name, token, max_age in [
            (cls.ACCESS_NAME, access, cls.ACCESS_MAX_AGE),
            (cls.REFRESH_NAME, refresh, cls.REFRESH_MAX_AGE),
        ]:
            response.set_cookie(
                key=name,
                value=token,
                httponly=cls.HTTPONLY,
                secure=cls.SECURE,
                samesite=cls.SAMESITE,
                max_age=max_age,
                path=cls.PATH,
            )

# 라우터 인스턴스
router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    req: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    1) Master 쿠키로 로그인
    2) TwitterUserService.get_user_info(screen_name) 호출 → internal ID 조회
    3) per-user 클라이언트 생성 → per-user 쿠키 저장
    4) AuthService.signup 호출 → JWT 쿠키 설정
    """
    # Master 클라이언트로 Twitter 로그인 검증
    master = TwitterClientService(user_internal_id="master")
    master.set_initial_cookies(req.ct0, req.auth_token)
    try:
        await master.ensure_login()
        logger.info("Master 로그인 성공")
    except Exception as e:
        logger.error("Master 로그인 실패: %s", e)
        raise BadRequestError("트위터 인증정보가 유효하지 않습니다.")

    # Twitter 내부 ID 조회
    twitter_master = TwitterUserService(client_service=master)
    try:
        info = await twitter_master.get_user_info(req.tweet_id)
        new_id = str(info["id"])
        logger.info("내부 ID 조회 성공: %s", new_id)
    except Exception as e:
        logger.error("ID 조회 실패: %s", e)
        raise BadRequestError("트위터 사용자 정보를 불러올 수 없습니다.")

    # Per-user 클라이언트 구성 및 쿠키 저장
    user_client = TwitterClientService(user_internal_id=new_id)
    user_client.set_initial_cookies(req.ct0, req.auth_token)
    try:
        await user_client.ensure_login()
        user_client.save_cookies_to_file()
        logger.info("Per-user 쿠키 저장 성공")
    except Exception as e:
        logger.warning("Per-user 쿠키 저장 실패: %s", e)

    # JWT 생성 및 쿠키 설정
    tokens = await AuthService(db, TwitterUserService(client_service=user_client)).signup(req)
    CookieConfig.set_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return TokenResponse(message="회원가입 및 로그인 성공", **tokens)

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    이메일 로그인 처리 후 JWT 쿠키를 설정
    """
    tokens = await AuthService(db).login(req.email, req.password)
    CookieConfig.set_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return TokenResponse(message="로그인 성공", **tokens)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
) -> TokenResponse:
    """
    리프레시 토큰 검증 후 새로운 액세스 토큰을 발급
    """
    token = request.cookies.get(CookieConfig.REFRESH_NAME)
    if not token:
        raise UnauthorizedError("리프레시 토큰이 없습니다.")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise JWTError
        now = datetime.now(timezone.utc)
        new_access = jwt.encode(
            {"sub": payload["sub"], "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES), "jti": payload["jti"], "type": "access"},
            settings.JWT_SECRET_KEY,
            algorithm="HS256"
        )
        CookieConfig.set_cookies(response, new_access, token)
        return TokenResponse(
            message="액세스 토큰 재발급 성공",
            access_token=new_access,
            refresh_token=token,
            token_type="bearer",
        )
    except JWTError:
        raise UnauthorizedError("리프레시 토큰이 유효하지 않습니다.")

@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    # current_user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    토큰 블랙리스트 등록 및 쿠키 삭제로 로그아웃 처리를 수행
    """
    auth_header: str = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            AuthService(db).logout(token)
        except Exception:
            logger.warning("토큰 블랙리스트 등록 실패")

    # 쿠키 삭제
    for name in [CookieConfig.ACCESS_NAME, CookieConfig.REFRESH_NAME]:
        response.delete_cookie(name, path=CookieConfig.PATH)
    return MessageResponse(message="로그아웃 성공")

@router.get("/check_login", response_model=MessageResponse)
async def check_login(current_user=Depends(get_current_user)) -> MessageResponse:
    """
    현재 JWT로 인증된 사용자의 이메일을 반환
    """
    return MessageResponse(message=f"Logged in as {current_user.email}")