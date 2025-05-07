# app/routers/protected.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.jwt.blocklist import jwt_blocklist

router = APIRouter(
    prefix="/protected",   # main.py 에서 "/api" 와 합쳐져 "/api/protected" 가 됩니다.
    tags=["Protected"],
)

# 로그인 엔드포인트에 맞추어 tokenUrl 지정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    1) Authorization 헤더의 Bearer 토큰을 디코딩
    2) sub(username)과 jti가 유효한지, 블록리스트에 올라있지 않은지 확인
    3) username 반환
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not username or not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰이 유효하지 않습니다."
            )
        if jti in jwt_blocklist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰이 무효화되었습니다."
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 인증 실패"
        )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="토큰 검증용 보호된 라우트",
)
def protected_route(current_user: str = Depends(get_current_user)):
    return {"message": f"Hello, {current_user}! This is a protected route."}