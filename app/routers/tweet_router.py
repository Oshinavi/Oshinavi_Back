import logging
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.llm_schema import ReplyResult
from app.schemas.tweet_schema import AutoReplyRequest, SendReplyRequest
from app.core.database import get_db_session
from app.dependencies import get_llm_service, get_current_user
from app.services.twitter.twitter_service import TwitterService
from app.services.llm.llm_service import LLMService
from app.repositories.user_repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tweets", tags=["Tweet"])


@router.get("/{screen_name}", status_code=status.HTTP_200_OK)
async def fetch_user_tweets(
    screen_name: str,
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService  = Depends(get_llm_service),
    current_user = Depends(get_current_user),   # 현재 로그인된 User 객체
):
    """
    1) 현재 로그인된 사용자의 이메일로 DB에서 유저 정보 조회
    2) 해당 유저의 twitter_user_internal_id를 꺼내 TwitterService 생성
    3) screen_name 대상의 최신 트윗 수집·저장
    """
    # 1) 로그인된 사용자 레코드 조회
    user_repo = UserRepository(db)
    me = await user_repo.find_by_email(current_user.email)
    if not me:
        raise HTTPException(status_code=404, detail="로그인된 사용자를 찾을 수 없습니다.")

    # 2) TwitterService 생성 (user_internal_id 주입)
    service = TwitterService(db, llm, user_internal_id=me.twitter_user_internal_id)

    # 3) 트윗 수집 수행
    try:
        tweets = await service.fetch_and_store_latest_tweets(screen_name)
        return tweets
    except Exception:
        logger.exception(f"트윗 조회 중 오류 발생: screen_name={screen_name}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "서버 오류로 트윗을 가져오지 못했습니다."},
        )


@router.post("/reply/auto_generate", status_code=status.HTTP_200_OK)
async def auto_generate_reply(
    request: AutoReplyRequest,
    current_user: User = Depends(get_current_user),
    llm: LLMService = Depends(get_llm_service),
):
    """LLM을 이용해 자동으로 리플라이 메시지를 생성합니다."""
    try:
        result: ReplyResult = await llm.reply(request.tweet_text)
        return {"reply": result.reply_text}
    except Exception:
        logger.exception("자동 리플라이 생성 중 오류 발생")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "자동 리플라이 생성에 실패했습니다."},
        )


@router.post("/reply/{tweet_id}", status_code=status.HTTP_200_OK)
async def send_reply(
    tweet_id: int,
    request: SendReplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
):
    """
    1) 로그인된 사용자의 twitter_user_internal_id 조회
    2) TwitterService 생성
    3) 지정된 tweet_id에 리플라이 전송
    """
    # 1) 로그인된 사용자 레코드 조회
    user_repo = UserRepository(db)
    me = await user_repo.find_by_email(current_user.email)
    if not me:
        raise HTTPException(status_code=404, detail="로그인된 사용자를 찾을 수 없습니다.")

    # 2) TwitterService 생성
    service = TwitterService(db, llm, user_internal_id=me.twitter_user_internal_id)

    # 3) 리플라이 전송
    service = TwitterService(db, llm, user_internal_id=current_user.twitter_user_internal_id)
    try:
        return await service.send_reply(tweet_id, request.tweet_text)
    except Exception:
        logger.exception(f"리플라이 전송 중 오류: {tweet_id}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "리플라이 전송 실패"},
        )