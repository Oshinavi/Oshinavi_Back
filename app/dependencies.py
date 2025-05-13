from typing import Set

from fastapi import Depends, HTTPException, status
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
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    data = auth_service.validate_token(token)
    user = await UserRepository(db).find_by_email(data.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user


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