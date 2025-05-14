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
from app.services.twitter.twitter_client_service import TwitterClientService
from app.schemas.auth_schema import SignupRequest, LoginRequest
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
        self.twitter_svc = twitter_svc

    # 회원가입
    async def signup(self, data: SignupRequest) -> dict:
        if data.password != data.cfpassword:
            raise BadRequestError("입력한 비밀번호가 일치하지 않습니다.")

        if await self.user_repo.find_by_email(data.email):
            raise ConflictError("이미 존재하는 이메일입니다.")

        if not self.twitter_svc or not await self.twitter_svc.user_exists(data.tweet_id):
            raise BadRequestError("트위터 서비스가 초기화되지 않았거나 유저를 찾을 수 없습니다.")

        internal_id = await self.twitter_svc.get_user_id(data.tweet_id)

        if await self.user_repo.has_user_by_internal_id(internal_id):
            raise ConflictError("이미 해당 트위터 ID로 가입된 사용자가 있습니다.")

        twitter_user = TwitterUser(
            twitter_internal_id=internal_id,
            twitter_id=data.tweet_id,
            username=data.username
        )
        await self.user_repo.add_twitter_user(twitter_user)

        hashed_pw = pwd_context.hash(data.password)
        user = User(
            username=data.username,
            email=data.email,
            password=hashed_pw,
            twitter_user_internal_id=internal_id
        )
        await self.user_repo.add_user(user)

        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"회원가입 커밋 실패: {e}")
            await self.db.rollback()
            raise

        try:
            tc = TwitterClientService(user_internal_id=internal_id)
            tc._client.set_cookies({
                "ct0": data.ct0,
                "auth_token": data.auth_token
            })
            tc.save_cookies_to_file()
            logger.info(f"Twitter cookies saved for user: {internal_id}")
        except Exception as e:
            logger.error(f"쿠키 저장 실패: {e}")

        return await self.login(data.email, data.password)

    # 로그인
    async def login(self, email: str, password: str) -> dict:
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

    # 로그아웃
    def logout(self, token: str) -> None:
        try:
            decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            jti = decoded.get("jti")
            if jti:
                jwt_blocklist.add(jti)
        except JWTError:
            logger.warning("토큰 디코딩 실패 (로그아웃 중 무시됨)")

    # 현재 로그인한 유저 정보 취득
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
