from sqlalchemy import Column, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class TweetLikes(Base):
    __tablename__ = "tweet_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    tweet_id = Column(
        BigInteger,
        ForeignKey("post.tweet_id", ondelete="CASCADE"),
        nullable=False,
    )

    # 🔁 User ↔ TweetLikes (1:N)
    user = relationship(
        "User",
        back_populates="likes",
        lazy="selectin"
    )

    # 🔁 Post ↔ TweetLikes (1:N)
    post = relationship(
        "Post",
        back_populates="likes",
        lazy="selectin"
    )