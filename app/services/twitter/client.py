import os
import json
import logging
from pathlib import Path
from twikit import Client

logger = logging.getLogger(__name__)

COOKIE_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "twitter_cookies.json"

class TwitterClientService:
    """
    Twikit 기반의 비동기 트위터 클라이언트 래퍼 클래스.
    쿠키 기반 로그인 유지 및 클라이언트 객체 제공 기능 포함.
    """
    def __init__(self):
        self._client = Client("en-US")
        self._logged_in = False

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
        if COOKIE_FILE_PATH.exists():
            try:
                with open(COOKIE_FILE_PATH, "r") as f:
                    cookies = json.load(f)
                self._client.set_cookies(cookies)
                logger.info("✅ Twitter 로그인 성공 (쿠키 기반)")
            except Exception as e:
                logger.error(f"❗ 쿠키 로딩 실패: {e}")
                raise RuntimeError("쿠키 파일 파싱에 실패했습니다.")
        else:
            raise FileNotFoundError("❗ 쿠키 파일이 존재하지 않습니다: 로그인 필요")

    def get_client(self) -> Client:
        """
        로그인된 Twikit 클라이언트 객체 반환
        """
        return self._client