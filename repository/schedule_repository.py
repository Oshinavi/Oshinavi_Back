import logging
from models import db, Schedule, UserOshi
from services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 스케쥴 정보 관련 DB 트랜잭션 정의
# ─────────────────────────────────────────────────────────────────────────────
class ScheduleRepository:
    def add_schedule(self, schedule: Schedule) -> None:
        db.session.add(schedule)

    # def edit_schedule(
    #         self,
    #         schedule_id: int,
    #         *,
    #         title: str,
    #         category: str,
    #         start_at: datetime,
    #         end_at: datetime,
    #         description: str | None,
    #         related_twitter_internal_id: str | None
    # ) -> Schedule | None:
    #     """
    #     schedule_id 로 일정을 조회한 뒤, 전달받은 필드들로 업데이트.
    #     업데이트된 Schedule 객체를 반환. 존재하지 않으면 None.
    #     """
    #     sched = Schedule.query.get(schedule_id)
    #     if not sched:
    #         return None
    #
    #     sched.title = title
    #     sched.category = category
    #     sched.start_at = start_at
    #     sched.end_at = end_at
    #     sched.description = description
    #     sched.related_twitter_internal_id = related_twitter_internal_id
    #
    #     db.session.commit()
    #     return sched

    # def delete_schedule(self, schedule_id: int, requesting_user_id: int) -> bool:
    #     """
    #     schedule_id 로 일정을 조회한 뒤,
    #     해당 일정을 생성한(created_by_user_id) 사용자와 요청 사용자가 같을 때만 삭제.
    #     삭제 성공 시 True, 그렇지 않으면 False.
    #     """
    #     schedule = Schedule.query.get(schedule_id)
    #     if not schedule:
    #         return False
    #
    #     # 소유자 확인
    #     if schedule.created_by_user_id != requesting_user_id:
    #         return False
    #
    #     db.session.delete(schedule)
    #     db.session.commit()
    #     return True

    def get_by_id(self, schedule_id: int) -> Schedule:
        """
        현재 로그인한 user_id 의 '오시'로 등록된 트위터 유저가 작성한 일정만 반환.
        """
        sched = Schedule.query.get(schedule_id)
        if not sched:
            logger.debug(f"Schedule {schedule_id} not found")
            raise NotFoundError(f"Schedule({schedule_id}) not found")
        return sched

    def list_by_twitter_id(self, twitter_internal_id: str) -> list[Schedule]:
        return (
            Schedule.query
            .filter_by(related_twitter_internal_id=twitter_internal_id)
            .order_by(Schedule.start_at)
            .all()
        )

    def remove(self, schedule: Schedule) -> None:
        db.session.delete(schedule)

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()

    def get_oshi_internal_id(self, user_id: int) -> str | None:
        uo = UserOshi.query.filter_by(user_id=user_id).first()
        return uo.oshi_internal_id if uo else None