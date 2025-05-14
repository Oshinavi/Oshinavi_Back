import logging

from app.services.twitter.twitter_client_service import TwitterClientService
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)

class TwitterUserService:
    """
    트위터 유저 정보 조회 서비스 클래스
    트위터 사용자의 기본 정보를 API를 통해 취득
    """
    def __init__(
        self,
        client_service: TwitterClientService  # 이제 내부 ID가 아니라 client_service만 받습니다
    ):
        """
        - client_service: TwitterClientService 인스턴스를 주입받기
        """
        self.client_service = client_service

    # 문자열 UTF-8 인코딩 복구
    @staticmethod
    def _fix_encoding(text: str | None) -> str | None:
        """
        잘못 Latin-1 로 디코딩된 UTF-8 문자열을 복구
        정상 문자열은 그대로 반환
        """
        if text is None:
            return None

        logger.debug(f"[_fix_encoding] BEFORE: {repr(text)}")
        try:
            fixed = text.encode("latin1").decode("utf-8")
            logger.debug(f"[_fix_encoding] AFTER : {repr(fixed)}")
            return fixed
        except UnicodeEncodeError:
            return text

    async def get_user_info(self, screen_name: str) -> dict:
        """
        지정된 screen_name의 사용자 정보를 조회
        """
        await self.client_service.ensure_login()
        client = self.client_service.get_client()
        user = await client.get_user_by_screen_name(screen_name)
        if not user:
            logger.warning(f"Twitter 사용자 '{screen_name}' 정보를 찾을 수 없음")
            raise NotFoundError(f"User '{screen_name}' not found")

        return {
            "id": user.id,
            "username": self._fix_encoding(user.name),
            "bio": self._fix_encoding(user.description),
            "profile_image_url": user.profile_image_url,
            "profile_banner_url": user.profile_banner_url,
        }

    async def get_user_id(self, screen_name: str) -> str:
        info = await self.get_user_info(screen_name)
        user_id = str(info["id"])
        logger.debug(f"[TwitterUserService] {screen_name} → id: {user_id}")
        return user_id

    async def user_exists(self, screen_name: str) -> bool:
        try:
            await self.client_service.ensure_login()
            client = self.client_service.get_client()
            user = await client.get_user_by_screen_name(screen_name)
            return user is not None and hasattr(user, "id")
        except Exception as e:
            logger.error(f"Twitter 존재 확인 실패: {e}")
            return False