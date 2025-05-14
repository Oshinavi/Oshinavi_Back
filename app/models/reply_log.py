from sqlalchemy import Column, Integer, BigInteger, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class ReplyLog(Base):
    """
    포스트에 대한 리플라이 기록 모델
    - 사용자가 특정 트윗(Post)에 보낸 답글 저장
    """
    __tablename__ = "reply_log"

    id: int = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="리플라이 기록 고유 ID"
    )
    post_tweet_id: int = Column(
        BigInteger,
        ForeignKey(
            "post.tweet_id",
            ondelete="CASCADE"  # Post 삭제 시 연관 리플라이도 자동 삭제
        ),
        nullable=False,
        doc="대상 포스트의 트윗 ID"
    )
    reply_text: str = Column(
        Text,
        nullable=False,
        doc="사용자가 작성한 답글 텍스트"
    )
    created_at: DateTime = Column(
        DateTime,
        server_default=func.now(),
        doc="리플라이 생성 시간"
    )

    # Post.posts -> ReplyLog.reply (One-to-Many 역관계)
    post = relationship(
        "Post",
        back_populates="replies",
        lazy="selectin",
        doc="연관된 Post 객체"
    )