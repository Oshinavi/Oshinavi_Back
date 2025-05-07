import logging
from app.services.twitter.client import TwitterClientService
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)

class TwitterUserService:
    """
    트위터 유저 정보 조회 서비스.
    """
    def __init__(self, client_service: TwitterClientService | None = None):
        # client_service를 주입받지 않으면 내부에서 기본 생성
        self.client_service = client_service or TwitterClientService()

    @staticmethod
    def _fix_encoding(s: str | None) -> str | None:
        """
        잘못 Latin-1 로 디코딩된 UTF-8 문자열을 복구한다.
        정상 문자열은 그대로 반환.
        """
        if s is None:
            return None
        print("[_fix_encoding] BEFORE:", repr(s))
        try:
            fixed = s.encode("latin1").decode("utf-8")
            print("[_fix_encoding] AFTER :", repr(fixed))
            return fixed
        except UnicodeEncodeError:
            # encode 실패 ⇒ 이미 정상 UTF-8
            return s

    async def get_user_info(self, screen_name: str) -> dict:
        await self.client_service.ensure_login()
        client = self.client_service.get_client()
        user = await client.get_user_by_screen_name(screen_name)
        if not user:
            logger.warning(f"❗ Twitter 사용자 '{screen_name}' 정보를 찾을 수 없음")
            raise NotFoundError(f"User '{screen_name}' not found")

        return {
            "id": user.id,
            # ⬇️ 인코딩 보정
            "username": self._fix_encoding(user.name),
            "bio": self._fix_encoding(user.description),
            "profile_image_url": user.profile_image_url,
            "profile_banner_url": user.profile_banner_url,
        }

    async def get_user_id(self, screen_name: str) -> str:
        info = await self.get_user_info(screen_name)
        user_id = str(info["id"])
        logger.debug(f"[TwitterUserService] {screen_name} → id: {info['id']}")
        return user_id

    async def user_exists(self, screen_name: str) -> bool:
        try:
            await self.client_service.ensure_login()
            client = self.client_service.get_client()
            u = await client.get_user_by_screen_name(screen_name)
            return u is not None and hasattr(u, "id")
        except Exception as e:
            logger.error(f"Twitter 존재 확인 실패: {e}")
            return False