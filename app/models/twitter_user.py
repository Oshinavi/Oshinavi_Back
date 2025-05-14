from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class TwitterUser(Base):
    """
    트위터 사용자(TwitterUser) 모델
    - 외부 트위터 계정 정보와 서비스 사용자(User) 간 연결 관리
    """
    __tablename__ = "twitter_user"

    twitter_internal_id: str = Column(
        String(120),
        primary_key=True,
        doc="서비스 내 고유 트위터 내부 ID"
    )
    twitter_id: str = Column(
        String(120),
        unique=True,
        nullable=False,
        doc="실제 트위터 사용자 ID(숫자)"
    )
    username: str = Column(
        String(120),
        nullable=False,
        doc="트위터 사용자 이름 또는 닉네임"
    )

    # 서비스 사용자(User)와 1:1 관계
    service_user = relationship(
        "User",
        back_populates="twitter_user",
        uselist=False,
        lazy="selectin",
        doc="연결된 서비스 사용자(User) 객체"
    )

    # 관심 사용자(UserOshi)와의 1:N 관계
    fans = relationship(
        "UserOshi",
        back_populates="oshi",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="이 트위터 유저를 관심으로 등록한 UserOshi 객체 목록"
    )

    # 게시글(Post)와의 1:N 관계
    posts = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="이 트위터 유저의 작성한 Post 목록"
    )

    # 일정(Schedule)와의 1:N 관계
    schedules = relationship(
        "Schedule",
        back_populates="related_twitter_user",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="이 트위터 유저와 연관된 일정 목록"
    )