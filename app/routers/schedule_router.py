import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.dependencies import get_current_user
from app.models.user import User
from app.models.schedule import Schedule
from app.schemas.schedule_schema import (
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
    ScheduleResponse
)
from app.services.schedule_service import ScheduleService
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.utils.exceptions import BadRequestError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/schedules",
    tags=["Schedule"],
)


def to_schedule_response(schedule: Schedule) -> ScheduleResponse:
    """
    Schedule 모델 인스턴스를 ScheduleResponse 스키마로 변환
    """
    return ScheduleResponse(
        id=schedule.id,
        title=schedule.title,
        category=schedule.category,
        start_at=schedule.start_at,
        end_at=schedule.end_at,
        description=schedule.description,
        related_twitter_internal_id=schedule.related_twitter_internal_id,
        related_twitter_screen_name=(
            schedule.related_twitter_user.twitter_id
            if schedule.related_twitter_user
            else None
        ),
        created_by_user_id=schedule.created_by_user_id,
    )


def _get_twitter_services_for_user(user: User) -> TwitterUserService:
    """
    현재 로그인된 유저의 twitter_internal_id를 기반으로
    TwitterClientService와 TwitterUserService를 초기화하여 반환
    """
    internal_id: Optional[str] = user.twitter_user_internal_id
    if not internal_id:
        # ApiError 중 하나(400 Bad Request) 던지기
        raise BadRequestError("먼저 트위터 계정을 연결해 주세요.")
    client_svc = TwitterClientService(user_internal_id=internal_id)
    return TwitterUserService(client_svc)


@router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_schedule(
    req: ScheduleCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> ScheduleResponse:
    """
    새로운 일정 생성
    - 트위터 연결 사용자 확인
    - ScheduleService를 통해 일정 생성
    """
    # 1) 로그인된 유저의 트위터 클라이언트 서비스 준비
    twitter_svc = _get_twitter_services_for_user(current_user)

    # 2) 스케줄 서비스 생성 (DB 세션 + twitter_svc 주입)
    schedule_service = ScheduleService(db, twitter_svc)

    # 3) 실제 일정 생성 로직 호출 (여기서 BadRequestError, NotFoundError 등 던져질 수 있음)
    new_schedule = await schedule_service.create_schedule(
        title=req.title,
        category=req.category,
        start_at=req.start_at,
        end_at=req.end_at,
        description=req.description,
        related_twitter_screen_name=req.related_twitter_screen_name,
        created_by_user_id=current_user.id,
    )
    return to_schedule_response(new_schedule)


@router.get("", response_model=List[ScheduleResponse])
async def list_my_oshi_schedules(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> List[ScheduleResponse]:
    """
    로그인 유저가 오시로 등록한 트위터 계정 기반으로 일정 조회
    """
    schedule_service = ScheduleService(db)
    schedules = await schedule_service.list_my_oshi_schedules(current_user.id)
    return [to_schedule_response(s) for s in schedules]


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    req: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ScheduleResponse:
    """
    기존 일정 수정
    - 소유권 확인 및 트위터 연결 사용자 확인
    """
    twitter_svc = _get_twitter_services_for_user(current_user)
    schedule_service = ScheduleService(db, twitter_svc)

    updated_schedule = await schedule_service.edit_schedule(
        schedule_id,
        current_user.id,
        **req.model_dump(exclude_unset=True)
    )
    return to_schedule_response(updated_schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_200_OK)
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    일정 삭제 처리
    - 소유권 확인 후 ScheduleService.delete_schedule 호출
    """
    schedule_service = ScheduleService(db)
    await schedule_service.delete_schedule(schedule_id, current_user.id)
    return {"message": "삭제 성공"}