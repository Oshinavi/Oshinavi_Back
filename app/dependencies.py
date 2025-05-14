# app/dependencies.py

from typing import Set
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.core.config import get_settings, Settings
from app.core.database import get_db_session
from app.jwt.blocklist import jwt_blocklist
from app.repositories.user_repository import UserRepository
from app.models.user import User

from app.services.llm.rag_service import RAGService
from app.services.llm.llm_service import LLMService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Dependency Injection 관련 로직


# ─── JWT 인증 ─────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str
    jti: str

class AuthService:
    def __init__(self, secret_key: str, blocklist: Set[str]):
        self._secret = secret_key
        self._blocklist = blocklist

    def validate_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
            data = TokenPayload(**payload)
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰 인증 실패")
        if data.jti in self._blocklist:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 무효화되었습니다.")
        return data

async def get_auth_service(
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(settings.JWT_SECRET_KEY, jwt_blocklist)

async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    1) 우선 Authorization 헤더에서 Bearer 토큰을 시도
    2) 실패하거나 없으면 쿠키 jwt_token 에서 토큰을 시도
    3) 토큰 검증 후 User 객체 반환
    """
    # 1) 헤더에서 토큰 추출 시도
    try:
        token = await oauth2_scheme(request)
    except HTTPException as header_exc:
        # 헤더에 토큰이 없거나 형식 오류 시, 쿠키에서 jwt_token 사용
        token = request.cookies.get("jwt_token")
        if not token:
            # 헤더 오류가 인증 실패라면 그대로 전달
            raise header_exc

    # 2) 토큰 검증
    data = auth_service.validate_token(token)

    # 3) DB에서 사용자 조회
    user = await UserRepository(db).find_by_email(data.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user

async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        from app.services.auth_service import AuthService as CoreAuthService
        return await CoreAuthService.get_current_user(token, db)
    except:
        return None


# ─── LLM 서비스 DI ────────────────────────────────────────────

async def get_llm_service(
    settings: Settings = Depends(get_settings),
) -> LLMService:
    """
    OpenAI AsyncOpenAI + FAISS 기반 RAGService 를 합친 LLMService 반환.
    """
    # OpenAI 클라이언트는 매번 생성해도 OK
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    rag = RAGService(
        index_path=settings.FAISS_INDEX_PATH,
        meta_path=settings.FAISS_META_PATH,
#       embedding_model_name=settings.EMBEDDING_MODEL_NAME,
        top_k=settings.RAG_TOP_K,
    )

    return LLMService(openai_client, rag)