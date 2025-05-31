import json
import logging
from pathlib import Path
from twikit import Client

logger = logging.getLogger(__name__)

MASTER_COOKIE_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "twitter_cookies_master.json"

class TwitterClientService:
    """
    Twikit 기반 비동기 트위터 클라이언트 래퍼.

    - MASTER_COOKIE_FILE 로 마스터 세션을 먼저 로드
    - set_initial_cookies() 로 per-request ct0/auth_token 덮어쓰기
    - ensure_login() 시, 마스터+per-user 쿠키를 클라이언트에 적용
    - save_cookies_to_file() 로 per-user 쿠키 파일 생성
    """
    def __init__(self, user_internal_id: str):
        self.user_id = user_internal_id
        self._client = Client("en-US")
        self._logged_in = False

        self.cookie_path = MASTER_COOKIE_FILE.parent / f"twitter_cookies_{self.user_id}.json"

    async def ensure_login(self) -> None:
        """
        한 번도 로그인되지 않았으면 마스터 쿠키 → per-user 쿠키 순으로 로드
        """
        if not self._logged_in:
            await self._load_cookies()
            self._logged_in = True

    async def _load_cookies(self) -> None:
        """
        1) 마스터 쿠키 로드
        2) per-user 쿠키가 있으면 덮어쓰기
        """
        # 1) 마스터 쿠키
        if not MASTER_COOKIE_FILE.exists():
            raise FileNotFoundError(f"Master cookie file not found: {MASTER_COOKIE_FILE}")
        master_cookies = json.loads(MASTER_COOKIE_FILE.read_text(encoding="utf-8"))
        self._client.set_cookies(master_cookies)
        logger.info("Master cookies loaded")

        # 2) per-user 쿠키(있으면)
        if self.cookie_path.exists():
            user_cookies = json.loads(self.cookie_path.read_text(encoding="utf-8"))
            self._client.set_cookies(user_cookies)
            logger.info("User cookies loaded: %s", self.cookie_path)

    def set_initial_cookies(self, ct0: str, auth_token: str) -> None:
        """
        프론트엔드에서 전달된 ct0/auth_token으로 덮어쓰기
        """
        self._client.set_cookies({"ct0": ct0, "auth_token": auth_token})

    def get_client(self) -> Client:
        """
        내부 Client 인스턴스 반환
        """
        return self._client

    def save_cookies_to_file(self) -> None:
        """
        현재 세션 쿠키를 per-user 파일로 저장
        """
        cookies = {cookie.name: cookie.value for cookie in self._client.http.cookies.jar}
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_path.write_text(json.dumps(cookies), encoding="utf-8")
        logger.info("Saved Twitter cookies JSON: %s", self.cookie_path)