from pydantic import BaseModel, Field


# ─── 트윗 관련 요청 스키마 정의 ─────────────────────────────────────────

class AutoReplyRequest(BaseModel):
    """
    자동 리플라이 생성 요청 모델입
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