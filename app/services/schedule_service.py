import logging
from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule
from app.services.twitter.user_service import TwitterUserService
from app.utils.exceptions import BadRequestError, UnauthorizedError

logger = logging.getLogger(__name__)

class ScheduleService:
    def __init__(self, db: AsyncSession, twitter_svc: TwitterUserService = None):
        self.db = db
        self.twitter_svc = twitter_svc or TwitterUserService()

    async def _resolve_internal_id(self, screen_name: str) -> str:
        logger.debug(f"Resolving internal ID for screen_name: {screen_name}")
        internal_id = await self.twitter_svc.get_user_id(screen_name)
        logger.debug(f"Resolved internal ID: {internal_id}")
        return internal_id

    async def create_schedule(
        self,
        title: str,
        category: str,
        start_at: datetime,
        end_at: datetime,
        description: str,
        related_twitter_screen_name: str,
        created_by_user_id: int
    ) -> Schedule:
        logger.info(f"Creating schedule for user_id={created_by_user_id}, title={title}")
        if end_at < start_at:
            logger.warning("Invalid schedule time range: end_at < start_at")
            raise BadRequestError("종료 시간이 시작 시간보다 앞설 수 없습니다.")

        internal_id = await self._resolve_internal_id(related_twitter_screen_name)
        logger.info("[create_schedule] 내부 ID 조회 완료: %s → %s", related_twitter_screen_name, internal_id)
        sched = Schedule(
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            description=description,
            related_twitter_internal_id=internal_id,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(sched)
        await self.db.commit()
        await self.db.refresh(sched)
        logger.info(f"Created schedule ID={sched.id}")
        return sched

    async def edit_schedule(
        self,
        schedule_id: int,
        user_id: int,
        title: str = None,
        category: str = None,
        start_at: datetime = None,
        end_at: datetime = None,
        description: str = None,
        related_twitter_screen_name: str = None,
    ) -> Schedule:
        logger.info(f"Editing schedule ID={schedule_id} by user_id={user_id}")
        sched = await self.db.get(Schedule, schedule_id)
        if not sched:
            logger.warning(f"Schedule not found: ID={schedule_id}")
            raise BadRequestError(f"일정 ID {schedule_id}를 찾을 수 없습니다.")
        if sched.created_by_user_id != user_id:
            logger.warning(f"Unauthorized edit attempt by user_id={user_id} on schedule ID={schedule_id}")
            raise UnauthorizedError("수정 권한이 없습니다.")
        if start_at and end_at and end_at < start_at:
            logger.warning("Invalid updated schedule time range: end_at < start_at")
            raise BadRequestError("종료 시간이 시작 시간보다 앞설 수 없습니다.")

        if related_twitter_screen_name:
            sched.related_twitter_internal_id = await self._resolve_internal_id(related_twitter_screen_name)

        if title: sched.title = title
        if category: sched.category = category
        if start_at: sched.start_at = start_at
        if end_at: sched.end_at = end_at
        if description: sched.description = description

        self.db.add(sched)
        await self.db.commit()
        await self.db.refresh(sched)
        logger.info(f"Updated schedule ID={schedule_id}")
        return sched

    async def delete_schedule(self, schedule_id: int, user_id: int) -> None:
        logger.info(f"Deleting schedule ID={schedule_id} by user_id={user_id}")
        sched = await self.db.get(Schedule, schedule_id)
        if not sched:
            logger.warning(f"Schedule not found for deletion: ID={schedule_id}")
            raise BadRequestError(f"일정 ID {schedule_id}를 찾을 수 없습니다.")
        if sched.created_by_user_id != user_id:
            logger.warning(f"Unauthorized delete attempt by user_id={user_id} on schedule ID={schedule_id}")
            raise UnauthorizedError("삭제 권한이 없습니다.")

        await self.db.delete(sched)
        await self.db.commit()
        logger.info(f"Deleted schedule ID={schedule_id}")

    async def list_my_oshi_schedules(self, user_id: int) -> List[Schedule]:
        from app.models.user_oshi import UserOshi
        logger.debug(f"Fetching oshi schedules for user_id={user_id}")
        stmt_uo = select(UserOshi).where(UserOshi.user_id == user_id)
        res_uo = await self.db.execute(stmt_uo)
        uo = res_uo.scalars().first()

        if not uo:
            logger.info(f"No oshi set for user_id={user_id}")
            return []

        stmt = select(Schedule).where(
            Schedule.related_twitter_internal_id == uo.oshi_internal_id
        ).order_by(Schedule.start_at)

        res = await self.db.execute(stmt)
        schedules = res.scalars().all()
        logger.info(f"Fetched {len(schedules)} schedules for oshi user_id={user_id}")
        return schedules