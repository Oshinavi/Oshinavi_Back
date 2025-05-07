from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)

    related_twitter_internal_id = Column(
        String(120),
        ForeignKey("twitter_user.twitter_internal_id", ondelete="SET NULL"),
        nullable=True
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )

    # 🔁 TwitterUser ↔ Schedule (1:N)
    related_twitter_user = relationship(
        "TwitterUser",
        back_populates="schedules",
        lazy="selectin"
    )

    # 🔁 User ↔ Schedule (1:N)
    creator = relationship(
        "User",
        back_populates="schedules",
        lazy="selectin"
    )