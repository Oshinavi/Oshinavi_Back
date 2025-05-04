import logging
from utils.async_utils import run_async
from repository.user_repository import UserRepository
from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from services.exceptions import NotFoundError
from models import TwitterUser

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 유저 오시정보 관련 로직 관리
# ─────────────────────────────────────────────────────────────────────────────
class UserService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.twitter_client = TwitterClientService()
        self.twitter_svc = TwitterUserService(self.twitter_client)

    def get_user_info(self, tweet_id: str) -> dict:
        twitter_data = run_async(self.twitter_svc.get_user_info(tweet_id))

        return {
            "tweet_internal_id": twitter_data["id"],
            "tweet_id": tweet_id,
            "username": twitter_data["username"],
            "bio": twitter_data["bio"],
            "profile_image_url": twitter_data["profile_image_url"],
            "profile_banner_url": twitter_data.get("profile_banner_url"),
        }

    def get_user_tweet_id(self, email: str) -> str:
        user = self.user_repo.find_by_email(email)
        if not user or not user.twitter_user:
            raise NotFoundError("사용자 정보가 없습니다.")
        return user.twitter_user.twitter_id

    def get_oshi(self, email: str) -> dict:
        # 이메일로 유저 정보 조회
        user = self.user_repo.find_by_email(email)
        if not user:
            raise NotFoundError("사용자를 찾을 수 없습니다.")

        # DB에 저장된 유저의 오시 정보 취득
        user_oshi = self.user_repo.get_user_oshi(user.id)
        if not user_oshi or not user_oshi.oshi:
            raise NotFoundError("오시가 등록되지 않았습니다.")

        # DB 테이블에서 가져온 정보 반환
        return {
            "oshi_tweet_id": user_oshi.oshi.twitter_id,
            "oshi_username": user_oshi.oshi.username
        }


    def set_oshi(self, email: str, oshi_tweet_id: str) -> None:
        # 이메일로 유저 정보 조회
        user = self.user_repo.find_by_email(email)
        if not user:
            raise NotFoundError("사용자를 찾을 수 없습니다.")

        user_info = run_async(self.twitter_svc.get_user_info(oshi_tweet_id))
        internal_id = user_info["id"]
        twitter_id = oshi_tweet_id
        username = user_info["username"]

        try:
            self.user_repo.get_twitter_user(internal_id)
        except NotFoundError:
            tu = TwitterUser(
                twitter_internal_id=internal_id,
                twitter_id=twitter_id,
                username=username
            )
            self.user_repo.add_twitter_user(tu)

        # 오시 정보 등록
        self.user_repo.upsert_user_oshi(user.id, internal_id)

        try:
            self.user_repo.commit()
        except Exception as e:
            logger.error(f"오시 저장 실패: {e}")
            self.user_repo.rollback()
            raise