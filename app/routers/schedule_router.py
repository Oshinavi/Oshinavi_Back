from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

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

router = APIRouter(prefix="/schedules", tags=["Schedule"])

def to_schedule_response(sched: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=sched.id,
        title=sched.title,
        category=sched.category,
        start_at=sched.start_at,
        end_at=sched.end_at,
        description=sched.description,
        related_twitter_internal_id=sched.related_twitter_internal_id,
        related_twitter_screen_name=sched.related_twitter_user.twitter_id if sched.related_twitter_user else None,
        created_by_user_id=sched.created_by_user_id,
    )

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    req: ScheduleCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    try:
        service = ScheduleService(db)
        sched = await service.create_schedule(
            title=req.title,
            category=req.category,
            start_at=req.start_at,
            end_at=req.end_at,
            description=req.description,
            related_twitter_screen_name=req.related_twitter_screen_name,
            created_by_user_id=current_user.id
        )
        return to_schedule_response(sched)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ScheduleResponse])
async def list_my_oshi_schedules(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    try:
        service = ScheduleService(db)
        schedules = await service.list_my_oshi_schedules(current_user.id)
        return [to_schedule_response(s) for s in schedules]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    req: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    try:
        service = ScheduleService(db)
        updated = await service.edit_schedule(
            schedule_id,
            current_user.id,
            **req.dict(exclude_unset=True)
        )
        return to_schedule_response(updated)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{schedule_id}", status_code=status.HTTP_200_OK)
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    try:
        service = ScheduleService(db)
        await service.delete_schedule(schedule_id, current_user.id)
        return {"message": "삭제 성공"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
