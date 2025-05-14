import os
import json
import logging
from pathlib import Path
from twikit import Client

logger = logging.getLogger(__name__)

COOKIE_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "twitter_cookies_1906210064702332928.json"

class TwitterClientService:
    """
    Twikit 기반의 비동기 트위터 클라이언트 래퍼 클래스.
    쿠키 기반 로그인 유지 및 클라이언트 객체 제공 기능 포함.
    """
    def __init__(self, user_internal_id: str):
        self.user_id = user_internal_id
        self._client = Client("en-US")
        self._logged_in = False

        self.cookie_path = (
                Path(__file__).resolve().parent.parent.parent
                / "config" / f"twitter_cookies_{self.user_id}.json"
        )

    async def ensure_login(self) -> None:
        """
        로그인 상태가 아니면 쿠키를 통해 로그인 수행
        """
        if not self._logged_in:
            await self._load_cookies_and_login()
            self._logged_in = True

    async def _load_cookies_and_login(self) -> None:
        """
        저장된 쿠키 파일을 로딩하여 Twikit 로그인 처리
        """
        if self.cookie_path.exists():
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            self._client.set_cookies(cookies)
            self._logged_in = True
            logger.info("✅ Twitter 로그인 성공 (쿠키 기반)")
            return
        raise FileNotFoundError("쿠키 파일이 없습니다.")

    def get_client(self) -> Client:
        """
        로그인된 Twikit 클라이언트 객체 반환
        """
        return self._client

    def save_cookies_to_file(self) -> None:
        """
        client.http.cookies 에 세팅된 dict 를
        JSON 으로 self.cookie_path 에 저장
        """
        cookies = self._client.http.cookies.get_dict()
        self.cookie_path.parent.mkdir(exist_ok=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f)