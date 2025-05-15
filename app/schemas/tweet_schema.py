from pydantic import BaseModel, Field
from typing import List, Optional


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