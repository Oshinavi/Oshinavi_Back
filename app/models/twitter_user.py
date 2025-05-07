from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class TwitterUser(Base):
    __tablename__ = "twitter_user"

    twitter_internal_id = Column(String(120), primary_key=True)
    twitter_id = Column(String(120), unique=True, nullable=False)
    username = Column(String(120), nullable=False)

    # 🔗 1:1 관계 - 서비스 연동된 유저
    service_user = relationship(
        "User",
        back_populates="twitter_user",
        uselist=False,
        lazy="selectin"
    )

    # 💖 1:N 관계 - 해당 트위터 유저를 좋아하는 유저들
    fans = relationship(
        "UserOshi",
        back_populates="oshi",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # 📝 1:N 관계 - 해당 트위터 유저의 트윗 목록
    posts = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # 📅 1:N 관계 - 등록된 일정
    schedules = relationship(
        "Schedule",
        back_populates="related_twitter_user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )