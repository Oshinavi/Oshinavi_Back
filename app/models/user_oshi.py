from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class UserOshi(Base):
    """
    유저의 오시(UserOshi) 모델
    - 사용자가 특정 트위터 계정을 오시(최애)로 등록한 정보를 저장
    """
    __tablename__ = "user_oshi"

    user_id: int = Column(
        Integer,
        ForeignKey(
            "user.id",
            ondelete="CASCADE"  # 유저가 삭제되면 관심 정보도 함께 삭제
        ),
        primary_key=True,
        doc="관심을 등록한 유저(User) ID"
    )
    oshi_internal_id: str = Column(
        String(120),
        ForeignKey(
            "twitter_user.twitter_internal_id",
            ondelete="CASCADE"  # 트위터 계정이 삭제되면 오시 정보도 삭제
        ),
        nullable=False,
        doc="오시 트위터 유저 트위터 내부 ID"
    )

    # User ↔ UserOshi (1:1)
    user = relationship(
        "User",
        back_populates="user_oshi",
        uselist=False,
        lazy="selectin",
        doc="오시 정보를 소유한 사용자(User) 객체"
    )

    # TwitterUser ↔ UserOshi (1:N)
    oshi = relationship(
        "TwitterUser",
        back_populates="fans",
        lazy="selectin",
        doc="유저가 관심 등록한 TwitterUser 객체"
    )