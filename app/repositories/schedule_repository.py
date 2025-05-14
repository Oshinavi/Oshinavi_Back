from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional

from app.models.schedule import Schedule
from app.models.user_oshi import UserOshi
from app.utils.exceptions import NotFoundError

class ScheduleRepository:
    """
    일정 데이터 액세스 객체(Repository)
    - Schedule 엔티티 CRUD 및 관련 조회 기능 제공
    """
    def __init__(self, session: Session):
        """
        - session: SQLAlchemy 세션 인스턴스
        """
        self.session = session

    def add_schedule(self, schedule: Schedule) -> None:
        """
        새 Schedule 객체를 세션에 추가
        """
        self.session.add(schedule)

    def get_schedule_by_id(self, schedule_id: int) -> Schedule:
        """
        id로 Schedule을 조회하여 반환
        """
        schedule = self.session.query(Schedule).get(schedule_id)
        if not schedule:
            raise NotFoundError(f"일정 ID {schedule_id}를 찾을 수 없습니다.")
        return schedule

    def delete_schedule(self, schedule: Schedule) -> None:
        """
        세션에서 Schedule 객체 삭제
        """
        self.session.delete(schedule)

    def list_schedules_by_twitter_id(self, twitter_internal_id: str) -> List[Schedule]:
        """
        주어진 트위터 내부 ID와 연관된 Schedule 목록을 반환
        - 시작 시간 기준 오름차순 정렬
        """
        return (
            self.session.query(Schedule)
            .filter(
                Schedule.related_twitter_internal_id == twitter_internal_id
            )
            .order_by(Schedule.start_at)
            .all()
        )

    def get_user_oshi_internal_id(self, user_id: int) -> Optional[str]:
        """
        UserOshi 테이블에서 유저의 oshi_internal_id를 조회하여 반환
        - 오시가 없으면 None 반환
        """
        user_oshi = (
            self.session.query(UserOshi)
            .filter(UserOshi.user_id == user_id)
            .first()
        )
        return user_oshi.oshi_internal_id if user_oshi else None

    def commit(self) -> None:
        """
        세션 변경 사항을 커밋
        """
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
