import logging
from twikit.errors import NotFound as TwikitNotFound

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
        client_service: TwitterClientService
    ):
        """
        - client_service: TwitterClientService 인스턴스를 주입받기
        """
        self.client_service = client_service

    # 문자열 UTF-8 인코딩 복구
    @staticmethod
    def _fix_encoding(text: str | None) -> str | None:
        """
        잘못 Latin-1로 디코딩된 UTF-8 문자열을 복구
        정상 문자열은 그대로 반환
        """
        if text is None:
            return None
        logger.debug("[_fix_encoding] BEFORE: %r", text)
        try:
            fixed = text.encode("latin1").decode("utf-8")
            logger.debug("[_fix_encoding] AFTER : %r", fixed)
            return fixed
        except UnicodeEncodeError:
            return text

    async def get_user_info(self, screen_name: str) -> dict:
        """
        지정된 screen_name의 사용자 정보를 조회
        반환값:
            {
                "id": str (internal ID),
                "username": str,
                "bio": str,
                "profile_image_url": str,
                "profile_banner_url": str,
                "followers_count": int,
                "following_count": int,
            }
        Raises:
            NotFoundError: 사용자 정보를 찾지 못한 경우
        """
        await self.client_service.ensure_login()
        client = self.client_service.get_client()
        try:
            user = await client.get_user_by_screen_name(screen_name)
        except TwikitNotFound:
            logger.warning(f"Twitter 사용자 '{screen_name}' 정보를 찾을 수 없음 (TwikitNotFound)")
            raise NotFoundError(f"User '{screen_name}' not found")
        except Exception as e:
            logger.error(f"트위터 API 호출 실패 ({screen_name}): {e}")
            raise

        if not user:
            logger.warning(f"Twitter 사용자 '{screen_name}' 정보를 찾을 수 없음 (None 반환)")
            raise NotFoundError(f"User '{screen_name}' not found")

        logger.info(f"[실제값은] {screen_name} → id: {user.id}")
        return {
            "id": user.id,
            "username": self._fix_encoding(user.name),
            "bio": self._fix_encoding(user.description),
            "profile_image_url": user.profile_image_url,
            "profile_banner_url": user.profile_banner_url,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
        }

    async def get_user_id(self, screen_name: str) -> str:
        """
        screen_name을 통해 internal ID(str)만 반환
        """
        info = await self.get_user_info(screen_name)
        user_id = str(info["id"])
        logger.info("[TwitterUserService] %s → id: %s", screen_name, user_id)
        return user_id

    async def user_exists(self, screen_name: str) -> bool:
        """
        해당 screenname 사용자가 존재하는지 확인
        """
        try:
            await self.client_service.ensure_login()
            client = self.client_service.get_client()
            user = await client.get_user_by_screen_name(screen_name)
            return user is not None and hasattr(user, "id")
        except TwikitNotFound:
            return False
        except Exception as e:
            logger.error(f"Twitter 존재 확인 실패: {e}")
            return False