import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.dependencies import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.twitter_user import TwitterUser
from app.repositories.user_repository import UserRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.schemas.user_schema import OshiResponse, OshiUpdateRequest, UserProfileResponse
from app.utils.exceptions import NotFoundError, BadRequestError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["User"])

@router.get(
    "/tweet_id",
    summary="현재 로그인한 사용자의 Twitter screen_name 반환",
    response_model=Dict[str, str],
)
async def get_my_tweet_id(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """
    로그인된 사용자의 Twitter screen_name(tweet_id) 반환
    """
    # 1) 내부 ID 확인
    internal_id = current_user.twitter_user_internal_id
    if not internal_id:
        raise NotFoundError("트위터 계정이 연결되어 있지 않습니다.")

    # 2) TwitterUser에서 screen_name 조회
    query = select(TwitterUser.twitter_id).where(
        TwitterUser.twitter_internal_id == internal_id
    )
    result = await db.execute(query)
    twitter_id = result.scalar_one_or_none()
    if not twitter_id:
        raise NotFoundError("트위터 정보를 찾을 수 없습니다.")
    return {"tweetId": twitter_id}

@router.get(
    "/me/oshi",
    response_model=OshiResponse,
    summary="내 오시 정보 조회",
)
async def get_my_oshi(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OshiResponse:
    """
    1) UserOshi에서 유저의 오시 내부 ID 조회
    2) TwitterUser에서 해당 정보 조회 후 반환
    """
    repo = UserRepository(db)
    user_oshi = await repo.find_user_oshi(current_user.id)
    if not user_oshi:
        raise NotFoundError("오시 정보가 없습니다.")

    query = select(TwitterUser).where(
        TwitterUser.twitter_internal_id == user_oshi.oshi_internal_id
    )
    result = await db.execute(query)
    tw_user = result.scalar_one_or_none()
    if not tw_user:
        raise NotFoundError("오시 트위터 정보를 찾을 수 없습니다.")

    return OshiResponse(
        oshi_screen_name=tw_user.twitter_id,
        oshi_username=tw_user.username,
    )

@router.put(
    "/me/oshi",
    response_model=OshiResponse,
    summary="내 오시 정보 업데이트",
)
async def update_my_oshi(
    payload: OshiUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OshiResponse:
    """
    1) TwitterUserService로 screen_name 유효성 검증 및 내부 ID 조회
    2) TwitterUser 테이블에 신규 사용자 추가 (존재하지 않을 경우)
    3) UserOshi 엔티티 upsert 및 DB 커밋
    """
    # 1) 서비스 초기화
    client_svc = TwitterClientService(user_internal_id=current_user.twitter_user_internal_id)
    twitter_svc = TwitterUserService(client_svc)

    # 2) 입력된 screen_name 검증
    info = await twitter_svc.get_user_info(payload.screen_name)
    new_internal_id = str(info["id"])

    # 3) TwitterUser upsert
    query = select(TwitterUser).where(
        TwitterUser.twitter_internal_id == new_internal_id
    )
    exists = (await db.execute(query)).scalar_one_or_none()
    if not exists:
        db.add(
            TwitterUser(
                twitter_internal_id=new_internal_id,
                twitter_id=payload.screen_name,
                username=info.get("username", ""),
            )
        )
        await db.flush()

    # 4) UserOshi upsert 및 커밋
    repo = UserRepository(db)
    await repo.upsert_user_oshi(current_user.id, new_internal_id)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestError("오시 정보 저장 중 오류가 발생했습니다.")

    return OshiResponse(
        oshi_screen_name=payload.screen_name,
        oshi_username=info.get("username", ""),
    )

@router.delete(
    "/me/oshi",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내 오시 정보 삭제",
)
async def delete_my_oshi(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    1) UserOshi 삭제
    2) DB 커밋
    3) 204 No Content 반환
    """
    repo = UserRepository(db)
    try:
        await repo.delete_user_oshi(current_user.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestError("오시 정보 삭제 중 오류가 발생했습니다.")

@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="외부 트위터 유저 프로필 조회 (로그인 선택)",
)
async def get_user_profile(
    tweet_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> UserProfileResponse:
    """
    1) 로그인 시도(선택적), 실패 시 public 클라이언트로 처리
    2) TwitterUserService.get_user_info로 프로필 조회
    3) UserProfileResponse 반환
    """
    # 1) 클라이언트 초기화
    user_internal = (
        current_user.twitter_user_internal_id
        if current_user and current_user.twitter_user_internal_id
        else "public"
    )
    client_svc = TwitterClientService(user_internal_id=user_internal)
    twitter_svc = TwitterUserService(client_svc)
    try:
        await client_svc.ensure_login()
    except FileNotFoundError:
        # 마스터 쿠키가 없는 경우 public 모드로만 응답
        pass

    # 2) 프로필 정보 조회 / 응답 생성
    info = await twitter_svc.get_user_info(tweet_id)
    return UserProfileResponse(
        twitter_internal_id=str(info.get("id", "")),
        twitter_id=tweet_id,
        username=info.get("username", ""),
        bio=info.get("bio", ""),
        profile_image_url=info.get("profile_image_url"),
        profile_banner_url=info.get("profile_banner_url"),
        followers_count=info.get("followers_count", 0),
        following_count=info.get("following_count", 0),
    )