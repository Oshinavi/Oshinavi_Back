import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.reply_log import ReplyLog
from app.models.twitter_user import TwitterUser

logger = logging.getLogger(__name__)


class TweetRepository:
    """
    트윗(Post) 및 관련 로그 저장/조회 기능 담당 (AsyncSession 기반)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tweet_ids(self) -> set[str]:
        """이미 저장된 트윗 ID 목록 조회"""
        stmt = select(Post.tweet_id)
        result = await self.db.execute(stmt)
        return {str(row) for row in result.scalars().all()}

    async def list_recent_posts(self, limit: int = 20) -> list[Post]:
        """전체 최근 트윗 조회 (작성자 관계 포함)"""
        stmt = (
            select(Post)
            .options(selectinload(Post.author))  # ✅ 관계 eager load
            .order_by(Post.tweet_date.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_by_username(self, twitter_id: str, limit: int = 20) -> list[Post]:
        """특정 트위터 ID를 가진 유저의 최근 트윗 조회 (작성자 관계 포함)"""
        stmt = (
            select(Post)
            .join(TwitterUser, Post.author_internal_id == TwitterUser.twitter_internal_id)
            .options(selectinload(Post.author))  # ✅ 관계 eager load
            .where(TwitterUser.twitter_id == twitter_id)
            .order_by(Post.tweet_date.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    def add_post(self, post: Post) -> None:
        """트윗 추가 (flush는 호출하지 않음)"""
        self.db.add(post)

    def add_reply_log(self, log: ReplyLog) -> None:
        """리플라이 로그 추가"""
        self.db.add(log)

    async def commit(self) -> None:
        """커밋"""
        try:
            await self.db.commit()
        except SQLAlchemyError as e:
            logger.error(f"DB 커밋 실패: {e}")
            await self.db.rollback()
            raise

    async def rollback(self) -> None:
        """롤백"""
        await self.db.rollback()