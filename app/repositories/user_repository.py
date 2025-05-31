from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.twitter_user import TwitterUser
from app.models.user_oshi import UserOshi
from app.utils.exceptions import NotFoundError

class UserRepository:
    """
    사용자 관련 데이터 액세스 담당 Repository 클래스
    - User, TwitterUser, UserOshi 엔티티 조회 및 생성/업데이트 기능 제공
    """
    def __init__(self, session: AsyncSession):
        """
        session: 비동기 SQLAlchemy 세션
        """
        self.session = session

    async def find_by_email(self, email: str) -> Optional[User]:
        """
        주어진 이메일과 일치하는 User 객체 반환
        """
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def exists_by_twitter_internal_id(self, internal_id: str) -> bool:
        """
        주어진 트위터 내부 id로 가입된 사용자가 있는지 확인
        """
        query = select(User).where(
            User.twitter_user_internal_id == internal_id
        )
        result = await self.session.execute(query)
        return result.scalars().first() is not None

    async def create_twitter_user(self, twitter_user: TwitterUser) -> None:
        """
        새 TwitterUser 엔티티를 세션에 추가
        """
        self.session.add(twitter_user)

    async def create_user(self, user: User) -> None:
        """
        새 User 엔티티를 세션에 추가
        """
        self.session.add(user)

    async def find_user_oshi(self, user_id: int) -> Optional[UserOshi]:
        """
        주어진 유저 id의 UserOshi(오시) 엔티티 반환
        """
        query = select(UserOshi).where(UserOshi.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def upsert_user_oshi(
            self,
            user_id: int,
            oshi_internal_id: str
    ) -> UserOshi:
        """
        UserOshi가 존재하면 업데이트하고 없으면 새로 생성하여 반환
        """
        existing = await self.find_user_oshi(user_id)
        if existing:
            existing.oshi_internal_id = oshi_internal_id
            return existing
        new_oshi = UserOshi(
            user_id=user_id,
            oshi_internal_id=oshi_internal_id
        )
        self.session.add(new_oshi)
        return new_oshi

    async def delete_user_oshi(self, user_id: int) -> None:
        """
        주어진 유저의 UserOshi 엔티티를 삭제
        """
        from app.models.user_oshi import UserOshi

        # 1) UserOshi 찾기
        query = select(UserOshi).where(UserOshi.user_id == user_id)
        result = await self.session.execute(query)
        existing = result.scalars().first()

        # 2) 있으면 삭제
        if existing:
            await self.session.delete(existing)
            await self.session.flush()

    async def find_twitter_user_by_internal_id(
            self,
            internal_id: str
    ) -> TwitterUser:
        """
        주어진 트위터 내부 id에 대응하는 TwitterUser 반환
        """
        query = select(TwitterUser).where(
            TwitterUser.twitter_internal_id == internal_id
        )
        result = await self.session.execute(query)
        twitter_user = result.scalars().first()
        if not twitter_user:
            raise NotFoundError(
                f"TwitterUser with id={internal_id} not found"
            )
        return twitter_user