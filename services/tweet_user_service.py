from services.tweet_client_service import TwitterClientService

# 트위터 내 유저 정보 취득 로직

class TwitterUserService:
    def __init__(self, client_service: TwitterClientService):
        self.client_service = client_service

    # username으로 해당 유저의 트위터 내부 id, 유저네임, 바이오 정보 조회 후 반환
    async def get_user_info(self, username: str):
        await self.client_service.ensure_login()
        try:
            client = self.client_service.get_client()
            user_info = await client.get_user_by_screen_name(username)
            if user_info:
                return {
                    "id": user_info.id,
                    "username": user_info.name,
                    "bio": user_info.description,
                    "profile_image_url": user_info.profile_image_url,
                    "profile_banner_url": user_info.profile_banner_url,
                }
            return None
        except Exception as e:
            print(f"유저 정보 불러오기 실패: {e}")
            return None

    # username으로 해당 유저의 트위터 내부 id 조회 후 반환
    async def get_user_id(self, username: str):
        info = await self.get_user_info(username)
        return info["id"] if info else None

    # username으로 실제 트위터상에 등록된 유저인지 여부 판별
    async def user_exists(self, username: str) -> bool:
        await self.client_service.ensure_login()
        try:
            client = self.client_service.get_client()
            user_info = await client.get_user_by_screen_name(username)
            print(f"🔍 user_info for '{username}': {user_info}")

            if user_info and hasattr(user_info, "id") and hasattr(user_info, "screen_name"):
                return True
            return False
        except Exception as e:
            print(f"Exception occured: {e}")
            return False