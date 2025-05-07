from sqlalchemy import Column, BigInteger, DateTime, Text, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Post(Base):
    __tablename__ = "post"

    tweet_id = Column(BigInteger, primary_key=True, index=True)

    author_internal_id = Column(
        String(120),
        ForeignKey("twitter_user.twitter_internal_id", ondelete="CASCADE"),  # 🔒 안전한 삭제 처리
        nullable=False
    )

    tweet_date = Column(DateTime, nullable=False)
    tweet_included_start_date = Column(DateTime, nullable=True)
    tweet_included_end_date = Column(DateTime, nullable=True)
    tweet_text = Column(Text, nullable=False)
    tweet_translated_text = Column(Text, nullable=False)
    tweet_about = Column(String(255), nullable=False)

    # 🧾 작성자 관계 (Many-to-One)
    author = relationship(
        "TwitterUser",
        back_populates="posts",
        lazy="joined"  # ← ORM 자동 조회 최적화 (필요 시 selectin으로 변경 가능)
    )

    # 💬 리플라이 관계 (One-to-Many)
    replies = relationship(
        "ReplyLog",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # ❤️ 좋아요 관계 (One-to-Many)
    likes = relationship(
        "TweetLikes",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin"
    )