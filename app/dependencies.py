import logging
from typing import Set, Optional

import base64
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, Settings
from app.core.database import get_db_session
from app.jwt.blocklist import jwt_blocklist
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.services.llm.pipeline_service import LLMPipelineService
from app.services.llm.rag_service import RAGService
from app.services.llm.llm_service import LLMService
from app.services.twitter.twitter_service import TwitterService

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class TokenPayload(BaseModel):
    """
   JWT 토큰 페이로드 모델
   - sub: 사용자 식별자 (이메일)
   - jti: 토큰 식별자 (JWT ID)
   """
    sub: str
    jti: str


class JWTAuthService:
    """
    JWT 토큰 검증 서비스
    - 토큰 디코딩 & 블랙리스트 등재 검사
    """
    def __init__(self, secret_key: str, blocklisted_jti: Set[str]):
        self._secret_key = secret_key
        self._blocklist = blocklisted_jti

    def validate_token(self, token: str) -> TokenPayload:
        """
        Bearer 토큰의 유효성을 검증하여 TokenPayload 반환
        """
        try:
            payload_data = jwt.decode(token, self._secret_key, algorithms=["HS256"])
            token_payload = TokenPayload(**payload_data)
        except JWTError:
            logger.warning("유효하지 않은 JWT 토큰: %s", token)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰 인증 실패"
            )

        if token_payload.jti in self._blocklist:
            logger.warning("블랙리스트 처리된 토큰: %s", token_payload.jti)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰이 무효화되었습니다."
            )
        return token_payload


async def get_auth_service(
    settings: Settings = Depends(get_settings)
) -> JWTAuthService:
    """
    AuthService 의존성 주입 함수
    - settings.env에서 JWT_SECRET_KEY와 blocklist를 받아 AuthService 생성
    """
    return JWTAuthService(settings.JWT_SECRET_KEY, jwt_blocklist)


async def get_current_user(
    request: Request,
    auth_service: JWTAuthService = Depends(get_auth_service),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    현재 요청의 사용자를 가져오는 종속성 함수
    1) Authorization 헤더의 Bearer 토큰 우선 사용
    2) 헤더에 없으면 쿠키의 'jwt_token' 사용
    3) validate_token() 호출 → TokenPayload 반환
    4) DB에서 email로 User 엔티티 조회 후 반환
    Raises:
        HTTPException(401) if token missing/invalid
        HTTPException(404) if user not found
    """
    # 1) Bearer 토큰 자동 추출 시도
    try:
        bearer_token = await oauth2_scheme(request)
    except HTTPException as header_exc:
        # 헤더에 없을 경우 쿠키 확인
        bearer_token = request.cookies.get("jwt_token")
        if not bearer_token:
            raise header_exc

    # 2) 토큰 검증 및 페이로드 획득
    token_info = auth_service.validate_token(bearer_token)

    # 3) DB에서 사용자 조회
    user = await UserRepository(db_session).find_by_email(token_info.sub)
    if not user:
        logger.error("토큰의 이메일(%s)로 사용자 조회 실패", token_info.sub)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    return user


async def get_current_user_optional(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    선택적 사용자 조회 함수
    - Authorization 헤더에 Bearer 토큰이 없거나 실패하면 None 반환
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None

    token = auth_header.split(" ", 1)[1]
    from app.services.auth_service import AuthService as CoreAuthService
    try:
        return await CoreAuthService.get_current_user(token, db_session)
    except Exception:
        # 토큰이 만료되었거나 유효하지 않으면 None 처리
        return None

def get_rag_service(
    settings: Settings = Depends(get_settings)
) -> RAGService:
    """
    RAGService 의존성 주입 함수
    - settings.env에서 FAISS_INDEX_PATH, FAISS_META_PATH, RAG_TOP_K 등을 받아 반환
    """
    return RAGService(
        index_path=settings.FAISS_INDEX_PATH,
        meta_path=settings.FAISS_META_PATH,
        top_k=settings.RAG_TOP_K,
    )

def get_pipeline_service(
    rag: RAGService = Depends(get_rag_service)
) -> LLMPipelineService:
    """
    LLMPipelineService 의존성 주입 함수
    - RAGService가 필요
    """
    return LLMPipelineService(rag)


async def get_llm_service(
    pipeline: LLMPipelineService = Depends(get_pipeline_service)
) -> LLMService:
    """
    LLMService 의존성 주입 함수
    - LLMPipelineService가 필요
    """
    return LLMService(pipeline)



async def get_twitter_service(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> TwitterService:
    """
    로그인된 사용자 정보를 바탕으로 TwitterService 인스턴스 생성
    1) DB에서 현재 사용자(User) 조회
    2) 해당 사용자의 twitter_user_internal_id를 TwitterService에 전달하여 반환
    Raises:
        HTTPException(404) if login된 사용자 정보가 없을 때
    """
    user_record = await UserRepository(db).find_by_email(current_user.email)
    if not user_record:
        logger.error("로그인된 사용자를 DB에서 찾을 수 없음: %s", current_user.email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="로그인된 사용자를 찾을 수 없습니다."
        )

    return TwitterService(
        db=db,
        llm_service=llm_service,
        user_internal_id=user_record.twitter_user_internal_id
    )