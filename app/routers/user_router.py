from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_current_user
from app.schemas.user import (
    OshiResponse,
    OshiUpdateRequest,
    UserProfileResponse
)
from app.repositories.user_repository import UserRepository
from app.services.twitter.user_service import TwitterUserService
from app.services.twitter.client import TwitterClientService
from app.core.database import get_db_session
from app.models.user import User
from app.models.twitter_user import TwitterUser
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/users", tags=["User"])


@router.get(
    "/tweet_id",
    summary="현재 로그인한 사용자의 Twitter screen_name 반환",
    status_code=status.HTTP_200_OK
)
async def get_my_tweet_id(
    current_user: User        = Depends(get_current_user),
    db: AsyncSession          = Depends(get_db_session),
):
    internal_id = current_user.twitter_user_internal_id
    if not internal_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="트위터 계정이 연결되어 있지 않습니다."
        )

    stmt = select(TwitterUser.twitter_id).where(
        TwitterUser.twitter_internal_id == internal_id
    )
    result = await db.execute(stmt)
    twitter_id = result.scalar_one_or_none()
    if not twitter_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="트위터 정보를 찾을 수 없습니다."
        )
    return {"tweetId": twitter_id}


@router.get(
    "/me/oshi",
    response_model=OshiResponse,
    summary="내 오시 정보 조회"
)
async def get_my_oshi(
    current_user: User        = Depends(get_current_user),
    db: AsyncSession          = Depends(get_db_session),
):
    repo = UserRepository(db)
    user_oshi = await repo.get_user_oshi(current_user.id)
    if not user_oshi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="오시 정보가 없습니다."
        )

    # twitter_user 테이블에서 oshi_internal_id로 사용자 정보 가져오기
    stmt = select(TwitterUser).where(
        TwitterUser.twitter_internal_id == user_oshi.oshi_internal_id
    )
    result = await db.execute(stmt)
    tw = result.scalar_one_or_none()
    if not tw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="오시 트위터 정보를 찾을 수 없습니다."
        )

    return {
        # screen_name
        "oshi_screen_name": tw.twitter_id,
        # display name
        "oshi_username": tw.username
    }


@router.put(
    "/me/oshi",
    response_model=OshiResponse,
    summary="내 오시 정보 업데이트"
)
async def update_my_oshi(
    payload: OshiUpdateRequest,
    current_user: User        = Depends(get_current_user),
    db: AsyncSession          = Depends(get_db_session),
):
    twitter_svc = TwitterUserService(
        client_service=TwitterClientService()
    )
    # 존재 확인 및 정보 조회
    info = await twitter_svc.get_user_info(payload.screen_name)
    internal_id = str(info["id"])

    # TwitterUser 테이블에 없으면 추가
    stmt = select(TwitterUser).where(TwitterUser.twitter_internal_id == internal_id)
    exists = (await db.execute(stmt)).scalar_one_or_none()
    if exists is None:
        db.add(TwitterUser(
            twitter_internal_id=internal_id,
            twitter_id=payload.screen_name,
            username=info["username"],
        ))
        await db.flush()

    # UserOshi 업데이트
    repo = UserRepository(db)
    await repo.upsert_user_oshi(current_user.id, internal_id)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="오시 정보 저장 중 오류가 발생했습니다."
        )


    return {
        "oshi_screen_name": payload.screen_name,
        "oshi_username": info["username"],
    }


@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="외부 트위터 유저 프로필 조회"
)
async def get_user_profile(
    tweet_id: str,
    client: TwitterUserService = Depends(
        lambda: TwitterUserService(TwitterClientService())
    )
):
    try:
        info = await client.get_user_info(tweet_id)
        return UserProfileResponse(
            twitter_internal_id=info["id"],
            twitter_id         =tweet_id,
            username           =info["username"],
            bio                =info["bio"],
            profile_image_url  =info["profile_image_url"],
            profile_banner_url =info["profile_banner_url"],
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )