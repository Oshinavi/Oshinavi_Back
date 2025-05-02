from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from utils.async_utils import run_async
from repository.user_repository import UserRepository


# ─────────────────────────────────────────────────────────────────────────────
# 유저 오시정보 관련 로직 관리
# ─────────────────────────────────────────────────────────────────────────────
class UserService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.twitter_client = TwitterClientService()
        self.twitter_user = TwitterUserService(self.twitter_client)

    def get_user_info(self, tweet_id: str):
        twitter_data = run_async(self.twitter_user.get_user_info(tweet_id))
        if not twitter_data:
            return None

        return {
            "tweet_internal_id": twitter_data["id"],
            "tweet_id": tweet_id,
            "username": twitter_data["username"],
            "bio": twitter_data["bio"],
            "profile_image_url": twitter_data["profile_image_url"],
            "profile_banner_url": twitter_data.get("profile_banner_url"),
        }

    def get_user_tweet_id(self, email: str) -> str | None:
        user = self.user_repo.find_user_by_email(email)
        if not user or user.twitter_user is None:
            return None
        return user.twitter_user.twitter_id

    def get_oshi(self, email: str):
        # 이메일로 유저 정보 조회
        user = self.user_repo.find_user_by_email(email)
        if not user:
            return None

        # DB에 저장된 유저의 오시 정보 취득
        user_oshi = self.user_repo.get_user_oshi(user.id)
        if not user_oshi or not user_oshi.oshi:
            return None

        # DB 테이블에서 가져온 정보 반환
        return {
            "oshi_tweet_id": user_oshi.oshi.twitter_id,
            "oshi_username": user_oshi.oshi.username
        }

    def set_oshi(self, email: str, oshi_tweet_id: str) -> tuple[bool, str]:
        # 이메일로 유저 정보 조회
        user = self.user_repo.find_user_by_email(email)
        if not user:
            return False, "사용자를 찾을 수 없습니다."

        user_info = run_async(self.twitter_user.get_user_info(oshi_tweet_id))
        if not user_info:
            return False, "해당 트위터 유저가 존재하지 않습니다."

        internal_id = user_info["id"]
        twitter_id = oshi_tweet_id
        username = user_info["username"]

        existing = self.user_repo.get_twitter_user_by_internal_id(internal_id)
        if not existing:
            self.user_repo.create_twitter_user(
                twitter_internal_id=internal_id,
                twitter_id=twitter_id,
                username=username
            )

        # 오시 정보 등록
        self.user_repo.upsert_user_oshi(user.id, oshi_internal_id=internal_id)
        return True, "오시 정보가 성공적으로 저장되었습니다."