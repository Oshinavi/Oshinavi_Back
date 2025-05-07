from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ScheduleCreateRequest(BaseModel):
    title: str = Field(..., description="일정 제목")
    category: str = Field(..., description="카테고리 (예: 일반, 방송, 라디오, 라이브, 음반 등)")
    start_at: datetime = Field(..., description="시작 일시")
    end_at: datetime = Field(..., description="종료 일시")
    description: Optional[str] = Field(None, description="설명")
    related_twitter_screen_name: str = Field(..., description="관련 트위터 스크린네임")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "팬미팅 공연",
                "category": "라이브",
                "start_at": "2025-05-10T20:00:00",
                "end_at": "2025-05-10T22:00:00",
                "description": "팬미팅 공연입니다.",
                "related_twitter_screen_name": "idol_account"
            }
        }
    }


class ScheduleUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, description="일정 제목")
    category: Optional[str] = Field(None, description="카테고리")
    start_at: Optional[datetime] = Field(None, description="시작 일시")
    end_at: Optional[datetime] = Field(None, description="종료 일시")
    description: Optional[str] = Field(None, description="설명")
    related_twitter_screen_name: Optional[str] = Field(None, description="관련 트위터 스크린네임")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "업데이트된 공연 일정",
                "category": "라이브",
                "start_at": "2025-05-10T21:00:00",
                "end_at": "2025-05-10T23:00:00",
                "description": "시간이 변경되었습니다.",
                "related_twitter_screen_name": "idol_account"
            }
        }
    }


class ScheduleResponse(BaseModel):
    id: int
    title: str
    category: str
    start_at: datetime
    end_at: datetime
    description: Optional[str]
    related_twitter_internal_id: Optional[str]
    related_twitter_screen_name: Optional[str] = None  # 관계 통해 동적으로 삽입
    created_by_user_id: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "title": "팬미팅 공연",
                "category": "라이브",
                "start_at": "2025-05-10T20:00:00",
                "end_at": "2025-05-10T22:00:00",
                "description": "팬미팅 공연입니다.",
                "related_twitter_internal_id": "1234567890",
                "related_twitter_screen_name": "idol_account",
                "created_by_user_id": 42
            }
        }
    }
