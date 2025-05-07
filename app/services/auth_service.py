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
from app.services.twitter.user_service import TwitterUserService
from app.services.twitter.client import TwitterClientService
from app.schemas.auth import SignupRequest
from app.utils.exceptions import (
    BadRequestError, ConflictError, NotFoundError, UnauthorizedError
)

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        twitter_svc: TwitterUserService | None = None
    ):
        self.db = db
        self.user_repo = UserRepository(db)
        # TwitterUserService를 파라미터로 받거나 기본 생성
        self.twitter_svc = twitter_svc or TwitterUserService(TwitterClientService())

    async def signup(self, data: SignupRequest) -> str:
        if data.password != data.cfpassword:
            raise BadRequestError("입력한 비밀번호가 일치하지 않습니다.")

        if await self.user_repo.find_by_email(data.email):  # EmailStr도 str의 서브클래스이므로 OK
            raise ConflictError("이미 존재하는 이메일입니다.")

        if not await self.twitter_svc.user_exists(data.tweet_id):
            raise NotFoundError("해당 트위터 유저를 찾을 수 없습니다.")

        internal_id = await self.twitter_svc.get_user_id(data.tweet_id)

        if await self.user_repo.has_user_by_internal_id(internal_id):
            raise ConflictError("이미 해당 트위터 ID로 가입된 사용자가 있습니다.")

        # TwitterUser 등록
        twitter_user = TwitterUser(
            twitter_internal_id=internal_id,
            twitter_id=data.tweet_id,
            username=data.username
        )
        await self.user_repo.add_twitter_user(twitter_user)

        # User 등록
        hashed_pw = pwd_context.hash(data.password)
        user = User(
            username=data.username,
            email=data.email,
            password=hashed_pw,
            twitter_user_internal_id=internal_id
        )
        await self.user_repo.add_user(user)

        # 커밋 후 바로 로그인 토큰 생성
        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"회원가입 커밋 실패: {e}")
            await self.db.rollback()
            raise

        # signup 후 자동으로 토큰 발급
        return await self.login(data.email, data.password)

    async def login(self, email: str, password: str) -> str:
        user = await self.user_repo.find_by_email(email)
        if not user or not pwd_context.verify(password, user.password):
            raise UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")

        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES)
        jti = f"{user.id}-{int(now.timestamp())}"

        payload = {"sub": email, "exp": expire, "jti": jti}
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    def logout(self, token: str) -> None:
        try:
            decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            jti = decoded.get("jti")
            if jti:
                jwt_blocklist.add(jti)
        except JWTError:
            logger.warning("토큰 디코딩 실패 (로그아웃 중 무시됨)")

    @staticmethod
    async def get_current_user(token: str, db: AsyncSession) -> User:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            email: str = payload.get("sub")
            jti: str = payload.get("jti")
            if not email or not jti:
                raise UnauthorizedError("유효하지 않은 토큰입니다.")

            if jti in jwt_blocklist:
                raise UnauthorizedError("이 토큰은 로그아웃되었습니다.")

            user_repo = UserRepository(db)
            user = await user_repo.find_by_email(email)
            if not user:
                raise NotFoundError("사용자를 찾을 수 없습니다.")
            return user

        except JWTError:
            raise UnauthorizedError("토큰 인증 실패")