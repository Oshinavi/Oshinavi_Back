from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, MessageResponse
from app.services.auth_service import AuthService
from app.core.database import get_db_session
from app.dependencies import get_current_user
from app.utils.exceptions import UnauthorizedError

router = APIRouter(
    prefix="/auth",    # ← router 자체에 "/auth"
    tags=["Auth"],
)

# 롤백 없이 raw token 을 받기 위한 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입 및 자동 로그인",
)
async def signup(
    req: SignupRequest,
    db: AsyncSession = Depends(get_db_session),
):
    # 1) 회원가입
    await AuthService(db).signup(req)
    # 2) 가입 직후 자동 로그인
    token = await AuthService(db).login(req.email, req.password)
    return {"message": "회원가입 및 로그인 성공", "token": token}


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="로그인",
)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    JSON body 로 email, password 를 받아 로그인합니다.
    """
    try:
        token = await AuthService(db).login(req.email, req.password)
        return {"message": "로그인 성공", "token": token}
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="로그아웃",
)
async def logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Authorization 헤더의 Bearer 토큰을 블록리스트에 추가합니다.
    """
    AuthService(db).logout(token)
    return {"message": "로그아웃 성공"}


@router.get(
    "/check_login",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="토큰 유효성 확인",
)
async def check_login(
    current_user = Depends(get_current_user),
):
    return {"message": f"Logged in as {current_user.email}"}