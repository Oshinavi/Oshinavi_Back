from typing import Set, Optional
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

# OAuth2 스킴 정의 (Authorization 헤더의 Bearer 토큰)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ─── JWT 인증 DI ─────────────────────────────────────────────────

class TokenPayload(BaseModel):
    """
   JWT 토큰 페이로드 모델
   - sub: 사용자 식별자 (이메일)
   - jti: 토큰 식별자 (JWT ID)
   """
    sub: str
    jti: str

class AuthService:
    """
    JWT 토큰 검증 서비스 클래스
    - 토큰을 디코딩하여 유효성을 검사
    - 블락리스트에 등재된 토큰 여부 확인
    """
    def __init__(self, secret_key: str, blocklisted_jti: Set[str]):
        self._secret_key = secret_key
        self._blocklist = blocklisted_jti

    def validate_token(self, token: str) -> TokenPayload:
        """
        JWT 토큰의 유효성을 검증, 페이로드 반환
        - 디코딩 실패 시 HTTP 401 예외 발생
        - blocklist 포함된 토큰은 무효화 처리
        """
        try:
            # 토큰 디코딩 및 BaseModel 검증
            payload_data = jwt.decode(token, self._secret_key, algorithms=["HS256"])
            token_payload = TokenPayload(**payload_data)
        except JWTError:
            # 토큰 인증 실패시 에러
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰 인증 실패"
            )
        # 로그아웃된 토큰인지 확인
        if token_payload.jti in self._blocklist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰이 무효화되었습니다."
            )
        return token_payload

async def get_auth_service(
    settings: Settings = Depends(get_settings),
) -> AuthService:
    """
    AuthService 의존성 주입 함수
    - 설정에서 비밀 키와 blacklist를 받아 AuthService 인스턴스를 반환
    """
    return AuthService(settings.JWT_SECRET_KEY, jwt_blocklist)

async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    현재 요청의 사용자 인증을 처리
    1) Authorization 헤더의 Bearer 토큰 우선 사용
    2) 헤더에 없으면 쿠키의 jwt_token 사용
    3) 토큰 검증 후 DB에서 사용자 엔티티를 조회하여 반환
    """
    
    # 1) 헤더에서 토큰 추출 시도
    try:
        bearer_token = await oauth2_scheme(request)
    except HTTPException as header_exc:
        # 헤더에 토큰이 없거나 형식 오류 시 쿠키에서 jwt_token 사용
        bearer_token = request.cookies.get("jwt_token")
        if not bearer_token:
            # 헤더 오류가 인증 실패라면 그대로 전달
            raise header_exc

    # 2) 토큰 검증
    token_info = auth_service.validate_token(bearer_token)

    # 3) DB에서 사용자 조회
    user = await UserRepository(db_session).find_by_email(token_info.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    return user

async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    선택적 사용자 조회
    - Authorization 헤더에 Bearer 토큰이 없거나 실패 시 None 반환
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        # CoreAuthService의 static 메서드를 사용해 사용자 조회
        from app.services.auth_service import AuthService as CoreAuthService
        return await CoreAuthService.get_current_user(token, db)
    except:
        return None


# ─── LLM 서비스 DI ────────────────────────────────────────────

async def get_llm_service(
    settings: Settings = Depends(get_settings),
) -> LLMService:
    """
    LLMService 의존성 주입 함수
    - OpenAI AsyncOpenAI 클라이언트 및 RAGService를 조합하여 반환
    """

    # OpenAI 클라이언트 생성
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # RAGService 생성
    rag = RAGService(
        index_path=settings.FAISS_INDEX_PATH,
        meta_path=settings.FAISS_META_PATH,
        top_k=settings.RAG_TOP_K,
    )
    return LLMService(openai_client, rag)