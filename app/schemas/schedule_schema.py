from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# ─── 일정 관련 요청/응답 스키마 정의 ─────────────────────────────────────

class ScheduleCreateRequest(BaseModel):
    """
    새로운 일정 생성 요청 모델
    - 필수: 제목(title), 분류(category), 시작/종료 일시, 관련 트위터 스크린네임
    - 선택: 설명(description)
    """
    title: str = Field(
        ..., description="일정 제목"
    )
    category: str = Field(
        ..., description="카테고리 (예: 일반, 방송, 라디오, 라이브, 음반 등)"
    )
    start_at: datetime = Field(
        ..., description="일정 시작 일시(ISO 8601 형식)"
    )
    end_at: datetime = Field(
        ..., description="일정 종료 일시(ISO 8601 형식)"
    )
    description: Optional[str] = Field(
        None, description="일정 상세 설명"
    )
    related_twitter_screen_name: str = Field(
        ..., description="해당 일정과 관련된 트위터 사용자의 스크린네임"
    )

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
    """
    기존 일정 수정 요청 모델
    """
    title: Optional[str] = Field(
        None, description="수정할 일정 제목"
    )
    category: Optional[str] = Field(
        None, description="수정할 카테고리"
    )
    start_at: Optional[datetime] = Field(
        None, description="수정할 시작 일시"
    )
    end_at: Optional[datetime] = Field(
        None, description="수정할 종료 일시"
    )
    description: Optional[str] = Field(
        None, description="수정할 설명"
    )
    related_twitter_screen_name: Optional[str] = Field(
        None, description="수정할 관련 트위터 스크린네임"
    )


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
    """
    일정 조회/응답 모델.
    - 데이터베이스의 Schedule 엔티티를 기반으로 변환
    """
    id: int = Field(
        ..., description="일정 고유 ID"
    )
    title: str = Field(
        ..., description="일정 제목"
    )
    category: str = Field(
        ..., description="일정 분류"
    )
    start_at: datetime = Field(
        ..., description="일정 시작 일시"
    )
    end_at: datetime = Field(
        ..., description="일정 종료 일시"
    )
    description: Optional[str] = Field(
        None, description="일정 상세 설명"
    )
    related_twitter_internal_id: Optional[str] = Field(
        None, description="관련 트위터 유저 내부 ID"
    )
    related_twitter_screen_name: Optional[str] = Field(
        None, description="관련 트위터 스크린네임"
    )
    created_by_user_id: int = Field(
        ..., description="일정 생성자(User) ID"
    )

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
