from services.tweet_client_service import TwitterClientService
from services.tweet_user_service import TwitterUserService
from utils.async_utils import run_async
from repository.user_repository import UserRepository

# 유저 오시정보 관련 로직 관리
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
        return user.tweet_id if user else None

    def get_oshi(self, email: str):
        # 이메일로 유저 정보 조회
        user = self.user_repo.find_user_by_email(email)
        if not user:
            return None

        # DB에 저장된 유저의 오시 정보 취득
        user_oshi = self.user_repo.get_user_oshi(user.id)
        if not user_oshi:
            return None

        return {
            "oshi_tweet_id": user_oshi.oshi_tweet_id,
            "oshi_username": user_oshi.oshi_username
        }

    def set_oshi(self, email: str, oshi_tweet_id: str) -> tuple[bool, str]:
        # 이메일로 유저 정보 조회
        user = self.user_repo.find_user_by_email(email)
        if not user:
            return False, "사용자를 찾을 수 없습니다."

        # 유저 유호성 확인
        is_valid = run_async(self.twitter_user.user_exists(oshi_tweet_id))
        if not is_valid:
            return False, "해당 트위터 유저가 존재하지 않습니다."

        # 유저 정보 취득
        user_info = run_async(self.twitter_user.get_user_info(oshi_tweet_id))
        if not user_info:
            return False, "유저 정보를 가져오지 못했습니다."

        # 오시 정보 등록
        self.user_repo.upsert_user_oshi(user.id, oshi_tweet_id, user_info["username"])
        return True, "오시 정보가 성공적으로 저장되었습니다."















# from models import db, User, UserOshi
# from services.tweet_user_service import TwitterUserService
# from services.tweet_client_service import TwitterClientService
# from utils.async_utils import run_async
#
# class UserService:
#     def __init__(self):
#         self.twitter_client_service = TwitterClientService()
#         self.twitter_user_service = TwitterUserService(self.twitter_client_service)
#
#     def get_user_info(self, tweet_id: str):
#         user_info = run_async(self.twitter_user_service.get_user_info(tweet_id))
#         if not user_info:
#             return None
#         return {
#             "tweet_internal_id": user_info["id"],
#             "tweet_id": tweet_id,
#             "username": user_info["username"],
#             "bio": user_info["bio"],
#         }
#
#     def get_user_tweet_id(self, email: str):
#         user = User.query.filter_by(email=email).first()
#         return user.tweet_id if user else None
#
#     def get_oshi(self, email: str):
#         user = User.query.filter_by(email=email).first()
#         if not user:
#             return None
#
#         user_oshi = UserOshi.query.filter_by(id=user.id).first()
#         if not user_oshi:
#             return None
#
#         return {
#             "oshi_tweet_id": user_oshi.oshi_tweet_id,
#             "oshi_username": user_oshi.oshi_username,
#         }
#
#     def set_oshi(self, email: str, oshi_tweet_id: str) -> tuple[bool, str]:
#         # 유저 유효성 확인
#         is_valid = run_async(self.twitter_user_service.user_exists(oshi_tweet_id))
#         if not is_valid:
#             return False, "No such user exists"
#
#         # 유저 정보 조회
#         user_info = run_async(self.twitter_user_service.get_user_info(oshi_tweet_id))
#         if not user_info:
#             return False, "Failed to retrieve user info"
#
#         oshi_username = user_info["username"]
#
#         # 현재 로그인 유저 조회
#         user = User.query.filter_by(email=email).first()
#         if not user:
#             return False, "사용자를 찾을 수 없습니다."
#
#         # 오시 정보 저장
#         user_oshi = UserOshi.query.filter_by(id=user.id).first()
#         if user_oshi:
#             user_oshi.oshi_tweet_id = oshi_tweet_id
#             user_oshi.oshi_username = oshi_username
#         else:
#             user_oshi = UserOshi(
#                 id=user.id,
#                 oshi_tweet_id=oshi_tweet_id,
#                 oshi_username=oshi_username
#             )
#             db.session.add(user_oshi)
#
#         db.session.commit()
#         return True, "오시 트윗 ID가 성공적으로 업데이트되었습니다."
