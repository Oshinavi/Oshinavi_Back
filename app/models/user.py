from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(120), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

    twitter_user_internal_id = Column(
        String(120),
        ForeignKey("twitter_user.twitter_internal_id", ondelete="SET NULL"),
        nullable=True,
        unique=True
    )

    # 🔁 TwitterUser ↔ User 관계 (1:1)
    twitter_user = relationship(
        "TwitterUser",
        back_populates="service_user",
        uselist=False,
        lazy="selectin"
    )

    # 🔁 User ↔ UserOshi 관계 (1:1)
    user_oshi = relationship(
        "UserOshi",
        back_populates="user",
        uselist=False,
        lazy="selectin"
    )

    # 🔁 User ↔ Schedule 관계 (1:N)
    schedules = relationship(
        "Schedule",
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # 🔁 User ↔ TweetLikes 관계 (1:N)
    likes = relationship(
        "TweetLikes",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )