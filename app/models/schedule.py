from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Schedule(Base):
    """
    유저 일정(Schedule) 모델입니다.
    - 이벤트 제목, 분류, 시간, 설명
    - 트위터 사용자 및 유저와의 관계 정의
    """
    __tablename__ = "schedules"

    id: int = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="일정 고유 ID"
    )
    title: str = Column(
        String(255),
        nullable=False,
        doc="일정 제목"
    )
    category: str = Column(
        String(100),
        nullable=False,
        doc="일정 분류 (예: '라이브', '방송' 등)"
    )
    start_at: DateTime = Column(
        DateTime,
        nullable=False,
        doc="일정 시작 시각"
    )
    end_at: DateTime = Column(
        DateTime,
        nullable=False,
        doc="일정 종료 시각"
    )
    description: str = Column(
        Text,
        nullable=True,
        doc="일정 상세 설명"
    )

    related_twitter_internal_id: str = Column(
        String(120),
        ForeignKey(
            "twitter_user.twitter_internal_id",
            ondelete="SET NULL"  # 연관된 트위터 사용자 삭제 시 NULL 처리
        ),
        nullable=True,
        doc="관련 트위터 사용자 내부 ID"
    )

    created_by_user_id: int = Column(
        Integer,
        ForeignKey(
            "user.id",
            ondelete="CASCADE"  # 유저 삭제 시 일정도 함께 삭제
        ),
        nullable=False,
        doc="일정 생성자(유저) ID"
    )

    # TwitterUser ↔ Schedule (1:N)
    related_twitter_user = relationship(
        "TwitterUser",
        back_populates="schedules",
        lazy="selectin",
        doc="연관된 트위터 사용자 객체"
    )

    # User ↔ Schedule (1:N)
    creator = relationship(
        "User",
        back_populates="schedules",
        lazy="selectin",
        doc="일정을 생성한 유저 객체"
    )
