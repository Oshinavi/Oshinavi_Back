import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from abc import ABC, abstractmethod

from datetime import datetime
from typing import Optional, List, Set, Dict, Any
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.reply_log import ReplyLog
from app.models.twitter_user import TwitterUser
from app.repositories.exceptions import (
    RepositoryError,
    DatabaseCommitError,
)

logger = logging.getLogger(__name__)


# ==================== 베이스 Repository ====================
class BaseRepository(ABC):
    """Repository 베이스 클래스"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def commit(self) -> None:
        """트랜잭션 커밋 (예외 처리 포함)"""
        try:
            await self.session.commit()
            logger.debug("DB 커밋 성공")
        except SQLAlchemyError as e:
            logger.error(f"DB 커밋 실패: {e}")
            await self.session.rollback()
            raise DatabaseCommitError(f"DB 커밋 중 오류 발생: {e}")

    async def rollback(self) -> None:
        """트랜잭션 롤백"""
        try:
            await self.session.rollback()
            logger.debug("DB 롤백 완료")
        except SQLAlchemyError as e:
            logger.error(f"DB 롤백 실패: {e}")
            raise RepositoryError(f"DB 롤백 중 오류 발생: {e}")


# ==================== 쿼리 빌더 클래스 ====================
class PostQueryBuilder:
    """Post 엔티티 쿼리 빌더"""

    @staticmethod
    def base_query_with_author():
        """작성자 정보를 포함한 기본 쿼리"""
        return select(Post).options(selectinload(Post.author))

    @staticmethod
    def build_cursor_query(
            twitter_id: str,
            last_date: Optional[datetime] = None,
            last_id: Optional[int] = None,
    ):
        """keyset pagination 쿼리 빌드"""
        query = (
            PostQueryBuilder.base_query_with_author()
            .join(TwitterUser, Post.author_internal_id == TwitterUser.twitter_internal_id)
            .where(TwitterUser.twitter_id == twitter_id)
        )

        if last_date and last_id:
            # keyset pagination: (tweet_date, tweet_id) < (last_date, last_id)
            query = query.where(
                or_(
                    Post.tweet_date < last_date,
                    and_(
                        Post.tweet_date == last_date,
                        Post.tweet_id < last_id,
                    )
                )
            )

        return query.order_by(
            Post.tweet_date.desc(),
            Post.tweet_id.desc()
        )

    @staticmethod
    def build_user_posts_query(twitter_id: str):
        """특정 사용자의 포스트 조회 쿼리"""
        return (
            PostQueryBuilder.base_query_with_author()
            .join(TwitterUser, Post.author_internal_id == TwitterUser.twitter_internal_id)
            .where(TwitterUser.twitter_id == twitter_id)
            .order_by(Post.tweet_date.desc())
        )


class ReplyLogQueryBuilder:
    """ReplyLog 엔티티 쿼리 빌더"""

    @staticmethod
    def build_delete_query(tweet_id: int):
        """특정 트윗의 답글 로그 삭제 쿼리"""
        return delete(ReplyLog).where(ReplyLog.post_tweet_id == tweet_id)


# ==================== 데이터 접근 인터페이스 ====================
class PostDataAccess(ABC):
    """Post 엔티티 데이터 접근 인터페이스"""

    @abstractmethod
    async def get_by_tweet_id(self, tweet_id: int) -> Optional[Post]:
        pass

    @abstractmethod
    async def list_tweet_ids(self) -> Set[int]:
        pass

    @abstractmethod
    async def list_recent_posts(self, limit: int) -> List[Post]:
        pass

    @abstractmethod
    async def list_posts_by_cursor(
            self, twitter_id: str, limit: int,
            last_date: Optional[datetime], last_id: Optional[int]
    ) -> List[Post]:
        pass


class ReplyLogDataAccess(ABC):
    """ReplyLog 엔티티 데이터 접근 인터페이스"""

    @abstractmethod
    async def delete_by_tweet_id(self, tweet_id: int) -> None:
        pass


# ==================== 구체적인 데이터 접근 구현 ====================
class PostDataAccessImpl(PostDataAccess):
    """Post 엔티티 데이터 접근 구현"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tweet_id(self, tweet_id: int) -> Optional[Post]:
        """tweet_id로 Post 조회"""
        try:
            result = await self.session.execute(
                select(Post).where(Post.tweet_id == tweet_id)
            )
            post = result.scalars().first()
            logger.debug(f"Post 조회: tweet_id={tweet_id}, found={bool(post)}")
            return post
        except SQLAlchemyError as e:
            logger.error(f"Post 조회 실패 (tweet_id={tweet_id}): {e}")
            raise RepositoryError(f"Post 조회 중 오류: {e}")

    async def list_tweet_ids(self) -> Set[int]:
        """모든 트윗 ID 집합 반환"""
        try:
            query = select(Post.tweet_id)
            result = await self.session.execute(query)
            tweet_ids = set(result.scalars().all())
            logger.debug(f"트윗 ID 목록 조회: count={len(tweet_ids)}")
            return tweet_ids
        except SQLAlchemyError as e:
            logger.error(f"트윗 ID 목록 조회 실패: {e}")
            raise RepositoryError(f"트윗 ID 목록 조회 중 오류: {e}")

    async def list_recent_posts(self, limit: int = 20) -> List[Post]:
        """최근 포스트 목록 조회"""
        try:
            query = (
                PostQueryBuilder.base_query_with_author()
                .order_by(Post.tweet_date.desc())
                .limit(limit)
            )
            result = await self.session.execute(query)
            posts = list(result.scalars().all())  # Sequence를 List로 명시적 변환
            logger.debug(f"최근 포스트 조회: limit={limit}, found={len(posts)}")
            return posts
        except SQLAlchemyError as e:
            logger.error(f"최근 포스트 조회 실패: {e}")
            raise RepositoryError(f"최근 포스트 조회 중 오류: {e}")

    async def list_posts_by_cursor(
            self,
            twitter_id: str,
            limit: int,
            last_date: Optional[datetime] = None,
            last_id: Optional[int] = None,
    ) -> List[Post]:
        """keyset pagination으로 포스트 목록 조회"""
        try:
            query = PostQueryBuilder.build_cursor_query(
                twitter_id, last_date, last_id
            ).limit(limit)

            result = await self.session.execute(query)
            posts = list(result.scalars().all())  # Sequence를 List로 명시적 변환

            logger.debug(
                f"커서 기반 포스트 조회: twitter_id={twitter_id}, "
                f"limit={limit}, found={len(posts)}"
            )
            return posts
        except SQLAlchemyError as e:
            logger.error(f"커서 기반 포스트 조회 실패: {e}")
            raise RepositoryError(f"커서 기반 포스트 조회 중 오류: {e}")

    async def list_posts_by_username(self, twitter_id: str, limit: int = 20) -> List[Post]:
        """특정 사용자의 포스트 목록 조회"""
        try:
            query = PostQueryBuilder.build_user_posts_query(twitter_id).limit(limit)
            result = await self.session.execute(query)
            posts = list(result.scalars().all())  # Sequence를 List로 명시적 변환

            logger.debug(
                f"사용자 포스트 조회: twitter_id={twitter_id}, "
                f"limit={limit}, found={len(posts)}"
            )
            return posts
        except SQLAlchemyError as e:
            logger.error(f"사용자 포스트 조회 실패: {e}")
            raise RepositoryError(f"사용자 포스트 조회 중 오류: {e}")


class ReplyLogDataAccessImpl(ReplyLogDataAccess):
    """ReplyLog 엔티티 데이터 접근 구현"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_by_tweet_id(self, tweet_id: int) -> None:
        """특정 트윗의 답글 로그 삭제"""
        try:
            query = ReplyLogQueryBuilder.build_delete_query(tweet_id)
            await self.session.execute(query)
            logger.debug(f"답글 로그 삭제: tweet_id={tweet_id}")
        except SQLAlchemyError as e:
            logger.error(f"답글 로그 삭제 실패 (tweet_id={tweet_id}): {e}")
            raise RepositoryError(f"답글 로그 삭제 중 오류: {e}")


# ==================== 엔티티 관리자 ====================
class PostManager:
    """Post 엔티티 관리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, post: Post) -> None:
        """Post 엔티티를 세션에 추가"""
        try:
            self.session.add(post)
            logger.debug(f"Post 추가: tweet_id={post.tweet_id}")
        except Exception as e:
            logger.error(f"Post 추가 실패: {e}")
            raise RepositoryError(f"Post 추가 중 오류: {e}")


class ReplyLogManager:
    """ReplyLog 엔티티 관리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, reply_log: ReplyLog) -> None:
        """ReplyLog 엔티티를 세션에 추가"""
        try:
            self.session.add(reply_log)
            logger.debug(f"답글 로그 추가: tweet_id={reply_log.post_tweet_id}")
        except Exception as e:
            logger.error(f"답글 로그 추가 실패: {e}")
            raise RepositoryError(f"답글 로그 추가 중 오류: {e}")


# ==================== 메인 Repository 클래스 ====================
class TweetRepository(BaseRepository):
    """
    비동기 트윗 데이터 액세스 객체
    - Post 및 ReplyLog 엔티티의 저장, 조회, 트랜잭션 처리 담당
    - 관심사 분리를 통한 클린 아키텍처 적용
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.post_data = PostDataAccessImpl(session)
        self.reply_log_data = ReplyLogDataAccessImpl(session)
        self.post_manager = PostManager(session)
        self.reply_log_manager = ReplyLogManager(session)

    # ==================== Post 관련 메서드 ====================
    async def get_post_by_tweet_id(self, tweet_id: int) -> Optional[Post]:
        """tweet_id로 Post 조회"""
        return await self.post_data.get_by_tweet_id(tweet_id)

    async def list_tweet_ids(self) -> Set[int]:
        """DB에 저장된 모든 트윗 ID를 집합으로 반환"""
        return await self.post_data.list_tweet_ids()

    async def list_recent_posts(self, limit: int = 20) -> List[Post]:
        """
        가장 최근에 저장된 Post 객체를 반환
        - 작성자 관계를 eager load하여 추가 조회 방지
        - 기본 정렬: tweet_date 내림차순
        """
        if limit <= 0:
            raise ValueError("limit은 0보다 큰 값이어야 합니다.")
        return await self.post_data.list_recent_posts(limit)

    async def list_posts_by_cursor(
            self,
            twitter_id: str,
            limit: int,
            last_date: Optional[datetime] = None,
            last_id: Optional[int] = None,
    ) -> List[Post]:
        """
        keyset pagination을 사용한 포스트 목록 조회

        Args:
            twitter_id: 조회할 트위터 사용자 ID
            limit: 조회할 최대 개수
            last_date: 마지막으로 조회한 포스트의 날짜
            last_id: 마지막으로 조회한 포스트의 ID

        Returns:
            List[Post]: 조회된 포스트 목록
        """
        if limit <= 0:
            raise ValueError("limit은 0보다 큰 값이어야 합니다.")

        return await self.post_data.list_posts_by_cursor(
            twitter_id, limit, last_date, last_id
        )

    async def list_posts_by_username(self, twitter_id: str, limit: int = 20) -> List[Post]:
        """
        특정 트위터 유저의 최근 Post 목록 반환
        - TwitterUser와 조인 후 필터링
        - 작성자 관계 eager load
        """
        if limit <= 0:
            raise ValueError("limit은 0보다 큰 값이어야 합니다.")

        return await self.post_data.list_posts_by_username(twitter_id, limit)

    def add_post(self, post: Post) -> None:
        """Post 객체를 세션에 추가"""
        if not isinstance(post, Post):
            raise ValueError("Post 인스턴스가 아닙니다.")
        self.post_manager.add(post)

    # ==================== ReplyLog 관련 메서드 ====================
    def add_reply_log(self, log: ReplyLog) -> None:
        """ReplyLog 객체를 세션에 추가"""
        if not isinstance(log, ReplyLog):
            raise ValueError("ReplyLog 인스턴스가 아닙니다.")
        self.reply_log_manager.add(log)

    async def delete_reply_log(self, tweet_id: int) -> None:
        """
        ReplyLog에 저장된 post_tweet_id == tweet_id인 행을 모두 삭제
        커밋도 함께 수행
        """
        try:
            await self.reply_log_data.delete_by_tweet_id(tweet_id)
            await self.commit()
            logger.info(f"답글 로그 삭제 및 커밋 완료: tweet_id={tweet_id}")
        except Exception as e:
            await self.rollback()
            logger.error(f"답글 로그 삭제 실패, 롤백 수행: tweet_id={tweet_id}, error={e}")
            raise

    # ==================== 트랜잭션 관련 메서드 ====================
    async def save_posts_batch(self, posts: List[Post]) -> None:
        """여러 Post를 배치로 저장"""
        if not posts:
            logger.info("저장할 포스트가 없습니다.")
            return

        try:
            for post in posts:
                self.add_post(post)

            await self.commit()
            logger.info(f"배치 포스트 저장 완료: count={len(posts)}")
        except Exception as e:
            await self.rollback()
            logger.error(f"배치 포스트 저장 실패, 롤백 수행: count={len(posts)}, error={e}")
            raise

    async def save_with_rollback_on_error(self, operation_name: str = "operation"):
        """
        컨텍스트 매니저를 사용한 안전한 저장
        오류 발생 시 자동 롤백

        Usage:
            async with repo.save_with_rollback_on_error("사용자 생성"):
                repo.add_post(post)
                # 다른 작업들...
        """

        class SaveContext:
            def __init__(self, repo, op_name):
                self.repo = repo
                self.op_name = op_name

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    try:
                        await self.repo.commit()
                        logger.info(f"{self.op_name} 완료")
                    except Exception as e:
                        await self.repo.rollback()
                        logger.error(f"{self.op_name} 커밋 실패, 롤백: {e}")
                        raise
                else:
                    await self.repo.rollback()
                    logger.error(f"{self.op_name} 실패, 롤백: {exc_val}")

        return SaveContext(self, operation_name)

    # ==================== 통계 및 유틸리티 메서드 ====================
    async def get_post_count_by_user(self, twitter_id: str) -> int:
        """특정 사용자의 포스트 개수 조회"""
        try:
            query = (
                select(Post.tweet_id)
                .join(TwitterUser, Post.author_internal_id == TwitterUser.twitter_internal_id)
                .where(TwitterUser.twitter_id == twitter_id)
            )
            result = await self.session.execute(query)
            count = len(result.scalars().all())
            logger.debug(f"사용자 포스트 개수: twitter_id={twitter_id}, count={count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"사용자 포스트 개수 조회 실패: {e}")
            raise RepositoryError(f"포스트 개수 조회 중 오류: {e}")

    async def get_latest_post_date(self, twitter_id: str) -> Optional[datetime]:
        """특정 사용자의 최신 포스트 날짜 조회"""
        try:
            query = (
                select(Post.tweet_date)
                .join(TwitterUser, Post.author_internal_id == TwitterUser.twitter_internal_id)
                .where(TwitterUser.twitter_id == twitter_id)
                .order_by(Post.tweet_date.desc())
                .limit(1)
            )
            result = await self.session.execute(query)
            latest_date = result.scalar_one_or_none()
            logger.debug(f"최신 포스트 날짜: twitter_id={twitter_id}, date={latest_date}")
            return latest_date
        except SQLAlchemyError as e:
            logger.error(f"최신 포스트 날짜 조회 실패: {e}")
            raise RepositoryError(f"최신 포스트 날짜 조회 중 오류: {e}")

    async def exists_post(self, tweet_id: int) -> bool:
        """특정 트윗 ID의 포스트 존재 여부 확인"""
        try:
            query = select(Post.tweet_id).where(Post.tweet_id == tweet_id)
            result = await self.session.execute(query)
            exists = result.scalar_one_or_none() is not None
            logger.debug(f"포스트 존재 확인: tweet_id={tweet_id}, exists={exists}")
            return exists
        except SQLAlchemyError as e:
            logger.error(f"포스트 존재 확인 실패: {e}")
            raise RepositoryError(f"포스트 존재 확인 중 오류: {e}")

    # ==================== 헬스체크 메서드 ====================
    async def health_check(self) -> Dict[str, Any]:
        """Repository 상태 확인"""
        try:
            # 기본 연결 테스트
            result = await self.session.execute(select(1))
            result.scalar()

            # 포스트 총 개수
            total_posts = len(await self.list_tweet_ids())

            return {
                "status": "healthy",
                "total_posts": total_posts,
                "connection": "ok",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"헬스체크 실패: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# ==================== Repository 팩토리 ====================
class RepositoryFactory:
    """Repository 인스턴스 생성 팩토리"""

    @staticmethod
    def create_tweet_repository(session: AsyncSession) -> TweetRepository:
        """TweetRepository 인스턴스 생성"""
        return TweetRepository(session)

    @staticmethod
    def create_repositories(session: AsyncSession) -> Dict[str, TweetRepository]:
        """모든 Repository 인스턴스를 포함한 딕셔너리 반환"""
        return {
            "tweet": TweetRepository(session),
            # 다른 Repository들도 여기에 추가 가능
        }


# ==================== 레거시 지원 (하위 호환성) ====================
def create_tweet_repository(session: AsyncSession) -> TweetRepository:
    """레거시 지원용 함수 - RepositoryFactory.create_tweet_repository 사용 권장"""
    return RepositoryFactory.create_tweet_repository(session)