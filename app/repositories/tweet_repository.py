import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.reply_log import ReplyLog
from app.models.twitter_user import TwitterUser

logger = logging.getLogger(__name__)

class TweetRepository:
    """
    비동기 트윗 데이터 액세스 객체
    - Post 및 ReplyLog 엔티티의 저장, 조회, 트랜잭션 처리 담당
    """
    def __init__(self, session: AsyncSession):
        """
        - session: 비동기 SQLAlchemy 세션
        """
        self.session = session

    async def get_post_by_tweet_id(self, tweet_id: int) -> Post | None:
        """
        tweet_id로 Post 하나 조회. 없으면 None 리턴.
        """

        result = await self.session.execute(
            select(Post).where(Post.tweet_id == tweet_id)
        )
        return result.scalars().first()

    async def list_tweet_ids(self) -> set[int]:
        """
        DB에 저장된 모든 트윗 ID를 문자열 집합으로 반환
        """
        query = select(Post.tweet_id)
        result = await self.session.execute(query)
        return set(result.scalars().all())

    async def list_recent_posts(self, limit: int = 20) -> list[Post]:
        """
        가장 최근에 저장된 Post 객체를 반환
        - 작성자 관계를 eager load하여 추가 조회 방지
        - 기본 정렬: tweet_date 내림차순
        - limit: 조회할 최대 개수
        """
        query = (
            select(Post)
            .options(selectinload(Post.author))
            .order_by(Post.tweet_date.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_posts_by_cursor(
            self,
            twitter_id: str,
            limit: int,
            last_date: Optional[datetime] = None,
            last_id: Optional[int] = None,
    ) -> list[Post]:
        """
        keyset pagination:
          - last_date, last_id 가 None 이면 맨 위부터(limit 개)
          - 아니면 (tweet_date, tweet_id) < (last_date, last_id) 인 것부터 limit 개
        """
        q = (
            select(Post)
            .join(TwitterUser, Post.author_internal_id == TwitterUser.twitter_internal_id)
            .where(TwitterUser.twitter_id == twitter_id)
        )

        if last_date and last_id:
            q = q.where(
                or_(
                    Post.tweet_date < last_date,
                    and_(
                        Post.tweet_date == last_date,
                        Post.tweet_id < last_id,
                    )
                )
            )

        q = (
            q.options(selectinload(Post.author))
            .order_by(Post.tweet_date.desc(), Post.tweet_id.desc())
            .limit(limit)
        )

        result = await self.session.execute(q)
        return result.scalars().all()

    async def list_posts_by_username(self, twitter_id: str, limit: int = 20) -> list[Post]:
        """
        특정 트위터 유저(twitter_id)의 최근 Post 목록 반환
        - TwitterUser와 조인 후 필터링
        - 작성자 관계 eager load
        """
        query = (
            select(Post)
            .join(
                TwitterUser,
                Post.author_internal_id == TwitterUser.twitter_internal_id
            )
            .options(selectinload(Post.author))
            .where(TwitterUser.twitter_id == twitter_id)
            .order_by(Post.tweet_date.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    def add_post(self, post: Post) -> None:
        """
        Post 객체 세션에 추가
        """
        self.session.add(post)

    def add_reply_log(self, log: ReplyLog) -> None:
        """
        리플라이 로그 세션에 추가
        """
        self.session.add(log)

    async def commit(self) -> None:
        """
        트랜잭션 커밋
        """
        try:
            await self.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"DB 커밋 실패: {e}")
            await self.session.rollback()
            raise

    async def rollback(self) -> None:
        """
        트랜잭션 롤백
        """
        await self.session.rollback()