from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional

from app.models.schedule import Schedule
from app.models.user_oshi import UserOshi
from app.utils.exceptions import NotFoundError


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, schedule: Schedule) -> None:
        self.db.add(schedule)

    def get_by_id(self, schedule_id: int) -> Schedule:
        schedule = self.db.query(Schedule).get(schedule_id)
        if not schedule:
            raise NotFoundError(f"일정 ID {schedule_id}를 찾을 수 없습니다.")
        return schedule

    def remove(self, schedule: Schedule) -> None:
        self.db.delete(schedule)

    def list_by_twitter_id(self, twitter_internal_id: str) -> List[Schedule]:
        return (
            self.db.query(Schedule)
            .filter(Schedule.related_twitter_internal_id == twitter_internal_id)
            .order_by(Schedule.start_at)
            .all()
        )

    def get_oshi_internal_id(self, user_id: int) -> Optional[str]:
        user_oshi = (
            self.db.query(UserOshi)
            .filter(UserOshi.user_id == user_id)
            .first()
        )
        return user_oshi.oshi_internal_id if user_oshi else None

    def save(self) -> None:
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
