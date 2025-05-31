from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.jwt.blocklist import jwt_blocklist
from app.utils.exceptions import UnauthorizedError

router = APIRouter(
    prefix="/protected",
    tags=["Protected"],
)

# 로그인 엔드포인트에 맞추어 tokenUrl 지정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def _validate_jwt_token(token: str) -> str:
    """
    JWT 토큰을 디코딩 및 검증하고 페이로드의 sub(사용자 식별자)를 반환
    - jti가 블랙리스트에 없고 필수 클레임이 모두 존재해야 함
    """
    try:
        # 토큰 디코딩
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not username or not jti:
            # 필수 클레임 누락 시 인증 실패
            raise UnauthorizedError("토큰이 유효하지 않습니다.")
        # 로그아웃된 토큰인지 확인
        if jti in jwt_blocklist:
            raise UnauthorizedError("토큰이 무효화되었습니다.")
        return username
    except JWTError:
        # 디코딩 오류 시 인증 실패
        raise UnauthorizedError("토큰 인증 실패")

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    종속성 함수: 요청 헤더의 Bearer 토큰을 검증하고 사용자 이름(sub)을 반환
    """
    return _validate_jwt_token(token)

@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="토큰 검증용 보호된 라우트",
)
async def protected_route(current_user: str = Depends(get_current_user)) -> dict:
    """
    인증된 사용자만 접근 가능한 테스트 엔드포인트
    - 종속성으로 token 검증을 수행하고, 사용자 이름을 이용해 환영 문구 반환
    """
    return {"message": f"Hello, {current_user}! This is a protected route."}