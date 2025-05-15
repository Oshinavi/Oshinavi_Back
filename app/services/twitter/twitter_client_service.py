import json
import logging
from pathlib import Path
from twikit import Client

logger = logging.getLogger(__name__)

# ─── 트위터 클라이언트 서비스 ───────────────────────────────────────────
class TwitterClientService:
    """
    Twikit 기반의 비동기 트위터 클라이언트 래퍼 클래스
    - 쿠키 파일을 통해 로그인 세션을 유지
    - Twikit Client 객체를 제공
    """
    def __init__(self, user_internal_id: str):
        """
        Args:
          user_internal_id: 사용자를 식별하기 위한 내부 ID (예: DB PK)
            - 이 ID를 기반으로 사용자별 쿠키 파일명이 생성됨
        """
        # 내부 사용자 ID 저장
        self.user_id = user_internal_id
        # Twikit 클라이언트 초기화 (locale 설정)
        self._client = Client("en-US")
        # 로그인 여부 플래그
        self._logged_in = False

        # 쿠키 파일 경로 설정
        self.cookie_path = (
            Path(__file__).resolve().parent.parent.parent
            / "config" / f"twitter_cookies_{self.user_id}.json"
        )

    async def ensure_login(self) -> None:
        """
        로그인 상태를 보장
        - 이미 로그인된 상태가 아니면 쿠키를 로드하여 로그인 수행
        """
        if not self._logged_in:
            await self._load_cookies_and_login()
            self._logged_in = True  # 로그인 플래그 설정

    async def _load_cookies_and_login(self) -> None:
        """
        내부 쿠키 파일을 로드하여 Twikit 로그인 처리
        """
        # 쿠키 파일 존재 여부 확인
        logger.info(f"✅ 쿠키 로드 시도: {self.cookie_path!r}, exists={self.cookie_path.exists()}")
        if self.cookie_path.exists():
            # 파일에서 JSON 형태의 쿠키 로드
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            # Twikit 클라이언트에 쿠키 설정
            self._client.set_cookies(cookies)
            logger.info("✅ Twitter 로그인 성공 (쿠키 기반)")
            return
        # 쿠키 파일이 없으면 예외 발생
        raise FileNotFoundError("쿠키 파일이 없습니다.")

    def get_client(self) -> Client:
        """
        로그인된 Twikit Client 객체를 반환
        - 호출 전에 ensure_login()으로 인증을 보장해야 함
        """
        return self._client

    def save_cookies_to_file(self) -> None:
        """
        현재 세션 쿠키를 JSON 파일로 저장
        - 쿠키 저장 경로에 디렉토리가 없으면 자동 생성
        """
        # HTTP 세션 쿠키를 dict로 추출
        cookies = self._client.http.cookies.get_dict()
        # 디렉토리 생성 (이미 존재해도 에러 없음)
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        # 쿠키를 JSON 파일로 저장
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json_text = json.dumps(cookies)
            f.write(json_text)