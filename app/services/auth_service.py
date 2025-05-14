import logging
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.jwt.blocklist import jwt_blocklist
from app.models.user import User
from app.models.twitter_user import TwitterUser
from app.repositories.user_repository import UserRepository
from app.services.twitter.twitter_user_service import TwitterUserService
from app.services.twitter.twitter_client_service import TwitterClientService
from app.schemas.auth_schema import SignupRequest
from app.utils.exceptions import (
    BadRequestError, ConflictError, NotFoundError, UnauthorizedError
)

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    인증 관련 서비스 클래스
    - 회원가입, 로그인, 로그아웃,
    - 현재 사용자 조회 기능을 제공
    """
    def __init__(
        self,
        db: AsyncSession,
        twitter_svc: TwitterUserService | None = None
    ):
        """
        - db: 비동기 DB 세션
        - twitter_svc: 주입된 TwitterUserService 인스턴스
        """
        self.db = db
        self.user_repo = UserRepository(db)
        self.twitter_svc = twitter_svc

    # 회원가입
    async def signup(self, data: SignupRequest) -> dict:
        """
        신규 사용자 회원가입 처리
        - 비밀번호 확인, 이메일 중복 확인
        - 트위터 ID 유효성 검증 후 내부 ID 확보
        - User 및 TwitterUser 엔티티 생성 및 저장
        - 트위터 쿠키 저장
        """
        # 1) 비밀번호 일치 여부 확인
        if data.password != data.cfpassword:
            raise BadRequestError("입력한 비밀번호가 일치하지 않습니다.")

        # 2) 이메일 중복 체크
        if await self.user_repo.find_by_email(data.email):
            raise ConflictError("이미 존재하는 이메일입니다.")

        # 3) 트위터 사용자 존재 확인
        if not self.twitter_svc or not await self.twitter_svc.user_exists(data.tweet_id):
            raise BadRequestError("트위터 서비스가 초기화되지 않았거나 유저를 찾을 수 없습니다.")

        # 4) 내부 ID 중복 가입 방지
        internal_id = await self.twitter_svc.get_user_id(data.tweet_id)
        if await self.user_repo.exists_by_twitter_internal_id(internal_id):
            raise ConflictError("이미 해당 트위터 ID로 가입된 사용자가 있습니다.")

        # 5) TwitterUser 엔티티 생성/저장
        twitter_user = TwitterUser(
            twitter_internal_id=internal_id,
            twitter_id=data.tweet_id,
            username=data.username
        )
        await self.user_repo.create_twitter_user(twitter_user)

        # 6) User 엔티티 생성/저장
        hashed_pw = pwd_context.hash(data.password)
        user = User(
            username=data.username,
            email=data.email,
            password=hashed_pw,
            twitter_user_internal_id=internal_id
        )
        await self.user_repo.create_user(user)

        # 7) DB 커밋 처리
        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"회원가입 커밋 실패: {e}")
            await self.db.rollback()
            raise

        # 8) 트위터 쿠키 설정 및 저장
        try:
            twitter_client = TwitterClientService(user_internal_id=internal_id)
            twitter_client._client.set_cookies({
                "ct0": data.ct0,
                "auth_token": data.auth_token
            })
            twitter_client.save_cookies_to_file()
            logger.info(f"Twitter cookies saved for user: {internal_id}")
        except Exception as e:
            logger.error(f"쿠키 저장 실패: {e}")

        # 회원가입 후 자동 로그인 토큰 발급
        return await self.login(data.email, data.password)

    async def login(self, email: str, password: str) -> dict:
        """
        사용자 로그인 처리
        - 이메일/비밀번호 검증
        - access/refresh 토큰 생성 및 반환
        """
        user = await self.user_repo.find_by_email(email)
        if not user or not pwd_context.verify(password, user.password):
            raise UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")

        now = datetime.now(timezone.utc)
        access_exp = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES)
        refresh_exp = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS)
        jti = f"{user.id}-{int(now.timestamp())}"

        access_payload = {"sub": email, "exp": access_exp, "jti": jti, "type": "access"}
        refresh_payload = {"sub": email, "exp": refresh_exp, "jti": jti, "type": "refresh"}

        access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    def logout(self, token: str) -> None:
        """
        사용자 로그아웃 처리
        - 토큰을 블락리스트에 추가하여 무효화
        """
        try:
            decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            jti = decoded.get("jti")
            if jti:
                jwt_blocklist.add(jti)
        except JWTError:
            logger.warning("토큰 디코딩 실패 (로그아웃 중 무시됨)")

    @staticmethod
    async def get_current_user(token: str, db: AsyncSession) -> User:
        """
        현재 로그인된 사용자를 조회
        - 전달된 JWT 토큰을 디코딩하여 유효성 검증
        - 블락리스트 확인 후 토큰이 유효한지 검사
        - DB에서 해당 사용자를 조회하여 반환
        """
        try:
            # 1) 토큰 디코딩 및 페이로드 추출
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            email: str = payload.get("sub")
            jti: str = payload.get("jti")
            if not email or not jti:
                # 필수 클레임 누락 시 예외 발생
                raise UnauthorizedError("유효하지 않은 토큰입니다.")

            # 로그아웃 처리된 토큰인지 확인
            if jti in jwt_blocklist:
                raise UnauthorizedError("이 토큰은 로그아웃되었습니다.")

            # 2) DB에서 사용자 조회
            user_repo = UserRepository(db)
            user = await user_repo.find_by_email(email)
            if not user:
                # 유저 없으면 예외발생
                raise NotFoundError("사용자를 찾을 수 없습니다.")
            return user
        except JWTError:
            # 토큰 디코딩 오류 시 인증 실패 예외
            raise UnauthorizedError("토큰 인증 실패")
