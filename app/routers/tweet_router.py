import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Union, Dict
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.llm_schema import ReplyResult
from app.schemas.tweet_schema import AutoReplyRequest, SendReplyRequest, TweetResponse
from app.core.database import get_db_session
from app.dependencies import get_llm_service, get_current_user
from app.services.twitter.twitter_service import TwitterService
from app.services.llm.llm_service import LLMService
from app.repositories.user_repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tweets", tags=["Tweet"])

@router.get("/{screen_name}", status_code=status.HTTP_200_OK, response_model=List[TweetResponse])
async def fetch_user_tweets(
    screen_name: str,
    db: AsyncSession = Depends(get_db_session),
    llm_service: LLMService  = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
) -> Union[List[Dict], JSONResponse]:
    """
    특정 Twitter 화면명(screen_name)의 최신 트윗을 수집하여 DB에 저장하고 반환합니다.
    1) 로그인 유저 레코드 조회
    2) TwitterService 생성
    3) 트윗 수집·저장 실행
    """
    # 1) 로그인된 사용자 엔티티 조회
    user_record = await UserRepository(db).find_by_email(current_user.email)
    if not user_record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "로그인된 사용자를 찾을 수 없습니다.")
    # 2) 서비스 생성
    twitter_service = TwitterService(db, llm_service, user_internal_id=user_record.twitter_user_internal_id)
    # 3) 트윗 수집 및 저장
    try:
        return await twitter_service.fetch_and_store_latest_tweets(screen_name)
    except Exception:
        logger.exception("[fetch_user_tweets] 트윗 조회 중 오류 발생: %s", screen_name)
        return JSONResponse(
            content={"error": "서버 오류로 트윗을 가져오지 못했습니다."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@router.post("/reply/auto_generate", status_code=status.HTTP_200_OK, response_model=None)
async def auto_generate_reply(
    req: AutoReplyRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> Union[Dict, JSONResponse]:
    """
    LLMService를 이용해 주어진 tweet_text에 대한 자동 응답 메시지를 생성합니다.
    """
    try:
        result: ReplyResult = await llm_service.reply(req.tweet_text)
        return {"reply": result.reply_text}
    except Exception:
        logger.exception("[auto_generate_reply] 자동 리플라이 생성 중 오류 발생")
        return JSONResponse(
            content={"error": "자동 리플라이 생성에 실패했습니다."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@router.post("/reply/{tweet_id}", status_code=status.HTTP_200_OK, response_model=None)
async def send_reply(
    tweet_id: int,
    req: SendReplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    llm_service: LLMService = Depends(get_llm_service),
) -> Union[Dict, JSONResponse]:
    """
    TwitterService를 통해 특정 트윗(tweet_id)에 리플라이를 전송합니다.
    1) 로그인 유저 레코드 조회
    2) TwitterService 생성
    3) 리플라이 전송 실행
    """
    # 1) 로그인된 사용자 엔티티 조회
    user_record = await UserRepository(db).find_by_email(current_user.email)
    if not user_record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "로그인된 사용자를 찾을 수 없습니다.")

    # 2) 서비스 생성
    twitter_service = TwitterService(db, llm_service, user_internal_id=user_record.twitter_user_internal_id)

    # 3) 리플라이 전송
    try:
        return await twitter_service.send_reply(tweet_id, req.tweet_text)
    except Exception:
        logger.exception("[send_reply] 리플라이 전송 중 오류: %s", tweet_id)
        return JSONResponse(
            content={"error": "리플라이 전송 실패"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
