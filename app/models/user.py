from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    """
    서비스 사용자(User) 모델
    - 애플리케이션의 기본 사용자 정보를 저장
    - 트위터 계정 연동, 관심 대상, 일정, 좋아요와의 관계 관리
    """
    __tablename__ = "user"

    id: int = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="사용자 고유 ID"
    )
    username: str = Column(
        String(120),
        unique=True,
        nullable=False,
        doc="서비스 내 사용자 이름(별칭)"
    )
    email: str = Column(
        String(120),
        unique=True,
        nullable=False,
        doc="사용자 이메일(로그인 ID)"
    )
    password: str = Column(
        String(255),
        nullable=False,
        doc="해시 처리된 비밀번호"
    )

    twitter_user_internal_id: str = Column(
        String(120),
        ForeignKey(
            "twitter_user.twitter_internal_id",
            ondelete="SET NULL"  # 연동된 트위터 사용자가 삭제되면 NULL 처리
        ),
        nullable=True,
        unique=True,
        doc="연동된 TwitterUser의 내부 ID"
    )

    # TwitterUser ↔ User (1:1)
    twitter_user = relationship(
        "TwitterUser",
        back_populates="service_user",
        uselist=False,
        lazy="selectin",
        doc="연동된 TwitterUser 객체"
    )

    # User ↔ UserOshi (1:1)
    user_oshi = relationship(
        "UserOshi",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        doc="사용자의 관심 대상(UserOshi) 객체"
    )

    # User ↔ Schedule (1:N)
    schedules = relationship(
        "Schedule",
        back_populates="creator",
        cascade="all, delete-orphan",  # 사용자 삭제 시 일정도 삭제
        lazy="selectin",
        doc="이 사용자가 생성한 일정 목록"
    )

    # User ↔ TweetLikes (1:N)
    likes = relationship(
        "TweetLikes",
        back_populates="user",
        cascade="all, delete-orphan",  # 사용자 삭제 시 좋아요도 삭제
        lazy="selectin",
        doc="이 사용자가 누른 좋아요 목록"
    )
