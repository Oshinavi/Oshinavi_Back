# app/repositories/user_repository.py

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.twitter_user import TwitterUser
from app.models.user_oshi import UserOshi
from app.utils.exceptions import NotFoundError

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()

    async def has_user_by_internal_id(self, internal_id: str) -> bool:
        result = await self.db.execute(
            select(User).where(User.twitter_user_internal_id == internal_id)
        )
        return result.scalars().first() is not None

    async def add_twitter_user(self, twitter_user: TwitterUser) -> None:
        self.db.add(twitter_user)

    async def add_user(self, user: User) -> None:
        self.db.add(user)

    async def get_user_oshi(self, user_id: int) -> Optional[UserOshi]:
        result = await self.db.execute(
            select(UserOshi).where(UserOshi.user_id == user_id)
        )
        return result.scalars().first()

    async def upsert_user_oshi(self, user_id: int, oshi_internal_id: str) -> UserOshi:
        existing = await self.get_user_oshi(user_id)
        if existing:
            existing.oshi_internal_id = oshi_internal_id
            return existing
        new = UserOshi(user_id=user_id, oshi_internal_id=oshi_internal_id)
        self.db.add(new)
        return new

    async def get_twitter_user_by_internal_id(self, internal_id: str) -> TwitterUser:
        result = await self.db.execute(
            select(TwitterUser).where(
                TwitterUser.twitter_internal_id == internal_id
            )
        )
        user = result.scalars().first()
        if not user:
            raise NotFoundError(
                f"TwitterUser with id={internal_id} not found"
            )
        return user