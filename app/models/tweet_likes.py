from sqlalchemy import Column, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class TweetLikes(Base):
    """TODO"""
    """
    !!아직 API 로직 정의되지 않았음.!!
    트윗 좋아요(TweetLikes) 모델
    - 사용자가 특정 트윗(Post)에 좋아요를 표시한 기록 저장
    """
    __tablename__ = "tweet_likes"

    id: int = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="좋아요 기록 고유 ID"
    )
    user_id: int = Column(
        Integer,
        ForeignKey(
            "user.id",
            ondelete="CASCADE"  # 사용자 삭제 시 연관 좋아요도 삭제
        ),
        nullable=False,
        doc="좋아요를 누른 사용자(User) ID"
    )
    tweet_id: int = Column(
        BigInteger,
        ForeignKey(
            "post.tweet_id",
            ondelete="CASCADE"  # 포스트 삭제 시 연관 좋아요도 삭제
        ),
        nullable=False,
        doc="좋아요 대상 트윗(Post) ID"
    )

    # User ↔ TweetLikes (1:N)
    user = relationship(
        "User",
        back_populates="likes",
        lazy="selectin",
        doc="좋아요를 누른 User 객체"
    )

    # Post ↔ TweetLikes (1:N)
    post = relationship(
        "Post",
        back_populates="likes",
        lazy="selectin",
        doc="좋아요 대상 Post 객체"
    )