from sqlalchemy import Column, BigInteger, DateTime, Text, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class Post(Base):
    """
    트윗 포스트 모델
    - 원본 트윗 정보 및 번역된 텍스트, 분류 결과를 저장
    - 작성자, 리플라이, 좋아요 관계 정의
    """
    __tablename__ = "post"

    tweet_id: int =  Column(
        BigInteger,
        primary_key=True,
        index=True,
        doc = "트위터 고유 ID"
    )

    author_internal_id: str = Column(
        String(120),
        ForeignKey(
            "twitter_user.twitter_internal_id",
            ondelete="CASCADE"  # 작성자 삭제 시 관련 포스트 자동 제거
        ),
        nullable=False,
        doc="작성자 내부 ID(TwitterUser.twitter_internal_id)"
    )

    tweet_date: DateTime = Column(
        DateTime,
        nullable=False,
        doc="트윗이 작성된 날짜 및 시간(한국시간)"
    )
    tweet_included_start_date: DateTime = Column(
        DateTime,
        nullable=True,
        doc="LLM이 추출한 이벤트 시작 날짜/시간"
    )
    tweet_included_end_date: DateTime = Column(
        DateTime,
        nullable=True,
        doc="LLM이 추출한 이벤트 종료 날짜/시간"
    )
    tweet_text: str = Column(
        Text,
        nullable=False,
        doc="원본 트윗 텍스트"
    )
    tweet_translated_text: str = Column(
        Text,
        nullable=False,
        doc="LLM이 번역한 트윗 텍스트"
    )
    tweet_about: str = Column(
        String(255),
        nullable=False,
        doc="트윗 분류 카테고리"
    )
    image_urls: str = Column(
        Text,
        nullable=True,
        doc="트윗에 포함된 이미지 URL 리스트 (JSON)"
    )
    schedule_checked: bool = Column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    schedule_title: str = Column(
        String(255),
        nullable=True,
        doc="일정의 제목"
    )
    schedule_description: str = Column(
        Text,
        nullable=True,
        doc="일정 상세 정보"
    )

    # User와의 관계 (Many-to-One)
    author = relationship(
        "TwitterUser",
        back_populates="posts",
        lazy="joined",  # 기본 조회 시 조인으로 작성자 정보 미리 로딩
        doc="작성자(TwitterUser) 관계"
    )

    # 리플라이 관계 (One-to-Many)
    replies = relationship(
        "ReplyLog",
        back_populates="post",
        cascade="all, delete-orphan",  # 포스트 삭제 시 리플라이도 삭제
        lazy="selectin",
        doc="연관 리플라이 목록"
    )

    # 좋아요 관계 (One-to-Many)
    likes = relationship(
        "TweetLikes",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="연관된 좋아요(いいね) 목록"
    )