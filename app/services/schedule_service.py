import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule
from app.models.user_oshi import UserOshi
from app.services.twitter.twitter_user_service import TwitterUserService
from app.utils.exceptions import BadRequestError, UnauthorizedError

logger = logging.getLogger(__name__)

class ScheduleService:
    """
    일정 관리 서비스 클래스
    - 유저 일정 생성, 수정, 삭제 기능
    """
    def __init__(
        self,
        db: AsyncSession,
        twitter_svc: Optional[TwitterUserService] = None
    ):
        """
        - db: 비동기 DB 세션
        - twitter_svc: 사용자 트위터 ID 확인용 서비스
        """
        self.db = db
        self.twitter_svc = twitter_svc

    async def _resolve_internal_id(self, screen_name: str) -> str:
        """
        screen_name으로 트위터 내부 ID를 조회.
        - twitter_svc 미설정 시 예외
        """
        if not self.twitter_svc:
            raise BadRequestError("트위터 서비스가 설정되어 있지 않습니다.")
        logger.debug(f"Resolving internal ID for screen_name={screen_name}")

        # 트위터 내부 id 조회
        internal_id = await self.twitter_svc.get_user_id(screen_name)
        if not internal_id:
            raise BadRequestError(f"트위터 유저를 찾을 수 없습니다: {screen_name}")
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
        """
        새로운 일정 생성 및 DB 저장
        1) 시작/종료 시간 검증
        2) 관련 트위터 사용자 내부 ID 조회
        3) Schedule 모델 생성 → commit → refresh → 반환
        """
        # 종료 시간이 시작 시간보다 앞설 경우 에러
        if end_at < start_at:
            raise BadRequestError("종료 시간이 시작 시간보다 앞설 수 없습니다.")

        # 1) 트위터 내부 ID 조회
        internal_id = await self._resolve_internal_id(
            related_twitter_screen_name
        )

        # 2) Schedule 인스턴스 생성
        sched = Schedule(
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            description=description,
            related_twitter_internal_id=internal_id,
            created_by_user_id=created_by_user_id,
        )
        # 3) DB 세션에 추가 및 커밋
        self.db.add(sched)
        await self.db.commit()
        await self.db.refresh(sched)
        return sched

    async def edit_schedule(
        self,
        schedule_id: int,
        user_id: int,
        title: Optional[str] = None,
        category: Optional[str] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        description: Optional[str] = None,
        related_twitter_screen_name: Optional[str] = None,
    ) -> Schedule:
        """
        기존 일정 수정
        1) Schedule 조회 (없으면 BadRequestError)
        2) 생성자(user_id)와 요청자(user_id) 일치 확인 (아니면 UnauthorizedError)
        3) 시간이 주어졌다면 유효성 재검증
        4) 관련 트위터 사용자 변경 시 내부 ID 재조회
        5) 각 필드별로 유효하면 변경 → commit → refresh → 반환
        """
        # 1) 일정 조회
        sched = await self.db.get(Schedule, schedule_id)
        if not sched:
            raise BadRequestError(f"일정 ID {schedule_id}를 찾을 수 없습니다.")

        # 2) 해당 일정을 생성한 유저인지 확인
        if sched.created_by_user_id != user_id:
            raise UnauthorizedError("수정 권한이 없습니다.")

        # 3) 시간 유효성 재검증
        if start_at and end_at and end_at < start_at:
            raise BadRequestError("종료 시간이 시작 시간보다 앞설 수 없습니다.")

        # 4) 관련 트위터 사용자 변경 시 내부 ID 재조회
        if related_twitter_screen_name:
            sched.related_twitter_internal_id = await self._resolve_internal_id(
                related_twitter_screen_name
            )

        # 5) 각 필드에 변경된 값 적용
        if title:
            sched.title = title
        if category:
            sched.category = category
        if start_at:
            sched.start_at = start_at
        if end_at:
            sched.end_at = end_at
        if description:
            sched.description = description

        # 6) 변경 사항 커밋 및 최신 상태 반영
        self.db.add(sched)
        await self.db.commit()
        await self.db.refresh(sched)
        return sched

    async def delete_schedule(self, schedule_id: int, user_id: int) -> None:
        """
        일정 삭제
        1) Schedule 조회 (없으면 BadRequestError)
        2) 생성자와 요청자(user_id) 일치 확인 (아니면 UnauthorizedError)
        3) delete → commit
        """
        sched = await self.db.get(Schedule, schedule_id)
        if not sched:
            raise BadRequestError(f"일정 ID {schedule_id}를 찾을 수 없습니다.")
        if sched.created_by_user_id != user_id:
            raise UnauthorizedError("삭제 권한이 없습니다.")

        await self.db.delete(sched)
        await self.db.commit()

    async def list_my_oshi_schedules(self, user_id: int) -> List[Schedule]:
        """
        오시 일정 조회
        1) UserOshi 테이블에서 해당 유저의 oshi_internal_id 조회
        2) 관련된 Schedule 모두 조회하여 시작 시간 기준 정렬 후 반환
        """
        # 1) UserOshi 조회
        user_oshi_query = select(UserOshi).where(UserOshi.user_id == user_id)
        user_oshi_result = await self.db.execute(user_oshi_query)
        user_oshi = user_oshi_result.scalars().first()
        if not user_oshi:
            return []

        # 2) Schedule 조회 → 정렬
        oshi_schedules_query = (
            select(Schedule)
            .where(Schedule.related_twitter_internal_id == user_oshi.oshi_internal_id)
            .order_by(Schedule.start_at)
        )
        schedules_result = await self.db.execute(oshi_schedules_query)
        return schedules_result.scalars().all()