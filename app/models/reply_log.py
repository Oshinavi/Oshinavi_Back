from sqlalchemy import Column, Integer, BigInteger, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class ReplyLog(Base):
    __tablename__ = "reply_log"

    id = Column(Integer, primary_key=True, index=True)
    post_tweet_id = Column(
        BigInteger,
        ForeignKey("post.tweet_id", ondelete="CASCADE"),
        nullable=False
    )
    reply_text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # 🔁 트윗(Post) ↔ 리플라이(ReplyLog) 관계
    post = relationship(
        "Post",
        back_populates="replies",
        lazy="selectin"
    )