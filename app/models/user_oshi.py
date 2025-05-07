from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class UserOshi(Base):
    __tablename__ = "user_oshi"

    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True
    )
    oshi_internal_id = Column(
        String(120),
        ForeignKey("twitter_user.twitter_internal_id", ondelete="CASCADE"),
        nullable=False
    )

    # 🔁 User ↔ UserOshi 관계
    user = relationship("User", back_populates="user_oshi", lazy="selectin")

    # 🔁 TwitterUser ↔ UserOshi 관계
    oshi = relationship("TwitterUser", back_populates="fans", lazy="selectin")