from pydantic import BaseModel, Field

class AutoReplyRequest(BaseModel):
    tweet_text: str = Field(..., min_length=1, description="자동 리플라이 생성을 위한 원본 트윗 텍스트")

class SendReplyRequest(BaseModel):
    tweet_text: str = Field(..., min_length=1, description="전송할 리플라이 텍스트")