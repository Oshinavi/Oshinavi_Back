import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db_session
from app.dependencies import get_current_user
from app.models.user import User
from app.models.twitter_user import TwitterUser
from app.repositories.user_repository import UserRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.schemas.user_schema import (
    OshiResponse,
    OshiUpdateRequest,
    UserProfileResponse
)
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["User"])


@router.get(
    "/tweet_id",
    summary="현재 로그인한 사용자의 Twitter screen_name 반환",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str]
)
async def get_my_tweet_id(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """
    로그인된 사용자의 Twitter screen_name(tweet_id) 반환합니다.
    """
    internal_id = current_user.twitter_user_internal_id
    if not internal_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="트위터 계정이 연결되어 있지 않습니다."
        )

    query = select(TwitterUser.twitter_id).where(
        TwitterUser.twitter_internal_id == internal_id
    )
    result = await db.execute(query)
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OshiResponse:
    """
    로그인 유저의 오시 정보를 반환
    """
    repo = UserRepository(db)
    user_oshi = await repo.find_user_oshi(current_user.id)
    if not user_oshi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="오시 정보가 없습니다."
        )
    query = select(TwitterUser).where(
        TwitterUser.twitter_internal_id == user_oshi.oshi_internal_id
    )
    result = await db.execute(query)
    tw_user = result.scalar_one_or_none()
    if not tw_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="오시 트위터 정보를 찾을 수 없습니다."
        )
    return OshiResponse(
        oshi_screen_name=tw_user.twitter_id,
        oshi_username=tw_user.username
    )


@router.put(
    "/me/oshi",
    response_model=OshiResponse,
    summary="내 오시 정보 업데이트"
)
async def update_my_oshi(
    payload: OshiUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OshiResponse:
    """
    로그인 유저의 오시의 Twitter id 업데이트
    - screen_name 유효성 확인
    - TwitterUser 테이블에 신규 추가
    - UserOshi 엔티티 upsert
    """

    # 1) 로그인된 유저의 쿠키 기반 TwitterClientService 생성
    client_svc = TwitterClientService(
        user_internal_id=current_user.twitter_user_internal_id
    )
    twitter_svc = TwitterUserService(client_svc)

    # 2) 입력된 screen_name 검증 및 내부 ID 조회
    info = await twitter_svc.get_user_info(payload.screen_name)
    new_internal_id = str(info["id"])

    # 3) TwitterUser 테이블에 신규 유저 추가
    query = select(TwitterUser).where(
        TwitterUser.twitter_internal_id == new_internal_id
    )
    exists = (await db.execute(query)).scalar_one_or_none()
    if not exists:
        db.add(TwitterUser(
            twitter_internal_id=new_internal_id,
            twitter_id=payload.screen_name,
            username=info["username"],
        ))
        await db.flush()

    # 4) UserOshi 업데이트
    repo = UserRepository(db)
    await repo.upsert_user_oshi(current_user.id, new_internal_id)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="오시 정보 저장 중 오류가 발생했습니다."
        )

    return OshiResponse(
        oshi_screen_name=payload.screen_name,
        oshi_username=info["username"]
    )


@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="외부 트위터 유저 프로필 조회 (로그인 필요)"
)
async def get_user_profile(
    tweet_id: str,
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """
    주어진 트위터 id로 외부 사용자 프로필 조회
    """

    # 1) 로그인된 유저의 쿠키 기반 TwitterClientService 생성
    client_svc = TwitterClientService(
        user_internal_id=current_user.twitter_user_internal_id
    )
    twitter_svc = TwitterUserService(client_svc)

    # 2) 트위터 API 호출
    try:
        info = await twitter_svc.get_user_info(tweet_id)
        return UserProfileResponse(
            twitter_internal_id=info["id"],
            twitter_id=tweet_id,
            username=info["username"],
            bio=info.get("bio"),
            profile_image_url=info.get("profile_image_url"),
            profile_banner_url=info.get("profile_banner_url"),
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )