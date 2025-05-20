from pydantic import BaseModel, Field, validator
from typing import List, Optional
import json


# ─── 트윗 관련 요청 스키마 정의 ─────────────────────────────────────────

class TweetResponse(BaseModel):
    tweet_id: int
    tweet_userid: str
    tweet_username: str
    tweet_date: str
    tweet_included_start_date: Optional[str]
    tweet_included_end_date: Optional[str]
    tweet_text: str
    tweet_translated_text: str
    tweet_about: str
    image_urls: List[str]
    profile_image_url: Optional[str]

    @validator('image_urls', pre=True)
    def parse_image_urls(cls, v):
        # v가 이미 List[str]인 경우(pass)
        if isinstance(v, list):
            return v
        # v가 None 또는 빈 문자열이면 빈 리스트로
        if not v:
            return []
        # JSON 문자열 → Python 리스트
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            # 파싱 실패 시 빈 리스트 또는 원본 문자열 리스트로
            return []

class TweetPageResponse(BaseModel):
    """
    페이지네이션된 트윗 응답 모델
    - tweets: 신규 트윗 리스트
    - next_cursor: 다음 페이지 호출용 cursor 토큰
    """
    tweets: List[TweetResponse]
    next_remote_cursor: Optional[str]
    next_db_cursor: Optional[str]

class TweetMetadataResponse(BaseModel):
    category: str
    start:    Optional[str]
    end:      Optional[str]
    schedule_title: Optional[str]
    schedule_description: Optional[str]

class ReplyResponse(BaseModel):
    """
    단일 리플(답글) 정보를 담는 모델
    """
    id: int
    screen_name: str
    user_name: str
    text: str
    profile_image_url: Optional[str]
    created_at: str
    is_mine: bool


# ─── 트윗 관련 요청 스키마 정의 ─────────────────────────────────────────

class AutoReplyRequest(BaseModel):
    """
    자동 리플라이 생성 요청 모델
    - 원본 트윗 텍스트를 입력받아 LLM을 통해 응답 메시지를 생성
    """
    tweet_text: str = Field(
        ...,
        min_length=1,
        description="자동 리플라이 생성을 위한 원본 트윗 텍스트"
    )

class SendReplyRequest(BaseModel):
    """
    리플라이 전송 요청 모델
    - 지정한 트윗 id에 대해 전송할 리플라이 텍스트를 입력받음
    """
    tweet_text: str = Field(
        ...,
        min_length=1,
        description="전송할 리플라이 텍스트"
    )