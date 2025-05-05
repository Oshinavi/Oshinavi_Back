import logging
import asyncio
from datetime import datetime

from repository.schedule_repository import ScheduleRepository
from services.exceptions import BadRequestError, UnauthorizedError
from models import Schedule
from services.tweet_user_service import TwitterUserService, TwitterClientService

logger = logging.getLogger(__name__)


class ScheduleService:
    def __init__(
        self,
        tweet_user_svc: TwitterUserService | None = None,
        repo: ScheduleRepository | None = None,
    ):
        # 의존성 주입으로 테스트 용이성↑
        self._tweet_svc = tweet_user_svc or TwitterUserService(client_service=TwitterClientService())
        self._repo      = repo or ScheduleRepository()

    def _resolve_twitter_internal_id(self, screen_name: str) -> str:
        """
        Twitter 스크린네임 → 내부 ID 변환.
        TweetUserService.get_user_id는 async이므로 asyncio.run으로 실행합니다.
        """
        try:
            return asyncio.run(self._tweet_svc.get_user_id(screen_name))
        except Exception as e:
            logger.error(f"Failed to resolve Twitter internal ID for '{screen_name}': {e}")
            raise BadRequestError("유효하지 않은 트위터 스크린네임입니다.")

    def create_schedule(
        self,
        *,
        title: str,
        category: str,
        start_at: datetime,
        end_at: datetime,
        description: str,
        related_twitter_screen_name: str,
        created_by_user_id: int,
    ) -> Schedule:
        # 1) 도메인 검증
        if end_at < start_at:
            raise BadRequestError("종료 시간이 시작 시간보다 앞설 수 없습니다.")

        # 2) 스크린네임 → 내부 ID
        internal_id = self._resolve_twitter_internal_id(related_twitter_screen_name)

        # 3) 엔티티 생성
        sched = Schedule(
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            description=description,
            related_twitter_internal_id=internal_id,
            created_by_user_id=created_by_user_id,
        )

        # 4) DB 저장
        try:
            self._repo.add_schedule(sched)
            self._repo.commit()
            return sched
        except Exception as e:
            logger.error(f"일정 생성 중 예외 발생: {e}")
            self._repo.rollback()
            raise

    def edit_schedule(
        self,
        schedule_id: int,
        user_id: int,
        *,
        title: str | None = None,
        category: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        description: str | None = None,
        related_twitter_screen_name: str | None = None,
    ) -> Schedule:
        # 1) 조회 및 권한 확인
        sched = self._repo.get_by_id(schedule_id)
        if sched.created_by_user_id != user_id:
            raise UnauthorizedError("수정 권한이 없습니다.")

        # 2) 도메인 검증
        if start_at and end_at and end_at < start_at:
            raise BadRequestError("종료 시간이 시작 시간보다 앞설 수 없습니다.")

        # 3) 변경 적용
        if title:    sched.title = title
        if category: sched.category = category
        if start_at: sched.start_at = start_at
        if end_at:   sched.end_at = end_at
        if description: sched.description = description
        if related_twitter_screen_name:
            sched.related_twitter_internal_id = self._resolve_twitter_internal_id(
                related_twitter_screen_name
            )

        # 4) DB 업데이트
        try:
            self._repo.commit()
            return sched
        except Exception as e:
            logger.error(f"일정 수정 중 예외 발생: {e}")
            self._repo.rollback()
            raise

    def delete_schedule(self, schedule_id: int, user_id: int) -> None:
        # 1) 조회 및 권한 확인
        sched = self._repo.get_by_id(schedule_id)
        if sched.created_by_user_id != user_id:
            raise UnauthorizedError("삭제 권한이 없습니다.")

        # 2) 삭제
        try:
            self._repo.remove(sched)
            self._repo.commit()
        except Exception as e:
            logger.error(f"일정 삭제 중 예외 발생: {e}")
            self._repo.rollback()
            raise

    def list_my_oshi_schedules(self, user_id: int) -> list[Schedule]:
        # 1) 이 사용자가 오시로 등록한 트위터 internal_id 조회
        internal_id = self._repo.get_oshi_internal_id(user_id)
        if not internal_id:
            return []
        # 2) 해당 ID로 일정 조회
        return self._repo.list_by_twitter_id(internal_id)