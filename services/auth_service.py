import logging
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from repository.user_repository import UserRepository
from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from utils.async_utils import run_async
from services.exceptions import BadRequestError, NotFoundError, ConflictError, UnauthorizedError
from models import User, TwitterUser

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        client_service = TwitterClientService()
        self.twitter_svc = TwitterUserService(client_service)

    # 유저 회원가입
    def signup(
            self,
            username: str,
            email: str,
            password: str,
            cfpassword: str,
            tweet_id: str
    ) -> None:

        # 1) 비밀번호 확인
        if password != cfpassword:
            raise BadRequestError("입력한 비밀번호가 일치하지 않습니다.")

        # 2) 이메일 중복 검사
        if self.user_repo.find_by_email(email):
            raise ConflictError("이미 존재하는 이메일입니다.")

        # 3) 트위터 유저 존재 확인
        if not run_async(self.twitter_svc.user_exists(tweet_id)):
            raise NotFoundError("해당 트위터 유저를 찾을 수 없습니다.")

        # 4) 내부 ID 조회
        try:
            internal_id = run_async(self.twitter_svc.get_user_id(tweet_id))
        except Exception as e:
            logger.error(f"트위터 내부 ID 조회 실패: {e}")
            raise NotFoundError("트위터 내부 ID 조회 실패")

        # 5) 이미 이 ID로 가입된 사용자가 있으면 거절
        try:
            self.user_repo.get_twitter_user(internal_id)
            raise ConflictError("이미 해당 트위터 ID로 가입된 사용자가 있습니다.")
        except NotFoundError:
            # 없으면 새로 추가
            tu = TwitterUser(
                twitter_internal_id=internal_id,
                twitter_id=tweet_id,
                username=username
            )
            self.user_repo.add_twitter_user(tu)

        # 6) 서비스 유저 생성
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            twitter_user_internal_id=internal_id
        )
        self.user_repo.add_user(user)

        # 7) 트랜잭션 커밋
        try:
            self.user_repo.commit()
        except Exception as e:
            logger.error(f"회원가입 커밋 실패: {e}")
            self.user_repo.rollback()
            raise

    # 로그인
    def login(self, email: str, password: str) -> str:
        user = self.user_repo.find_by_email(email)
        if not user or not check_password_hash(user.password, password):
            raise UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")
        return create_access_token(identity=email)

    # 로그아웃
    def logout(self, identity: str) -> None:
        # JWT 차단/삭제는 컨트롤러가 담당
        return