import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.llm_schema import ReplyResult
from app.schemas.tweet_schema import AutoReplyRequest, SendReplyRequest
from app.core.database import get_db_session
from app.dependencies import get_llm_service
from app.services.twitter.twitter_service import TwitterService
from app.services.llm.llm_service import LLMService

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tweets", tags=["Tweet"])


@router.get("/{screen_name}", status_code=status.HTTP_200_OK)
async def fetch_user_tweets(
    screen_name: str,
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService  = Depends(get_llm_service),
):
    """특정 유저의 최신 트윗을 수집하고 저장합니다."""
    service = TwitterService(db, llm)
    try:
        tweets = await service.fetch_and_store_latest_tweets(screen_name)
        return tweets
    except Exception as e:
        # 예외 상세 로그 출력
        logger.exception(f"트윗 조회 중 오류 발생: screen_name={screen_name}")
        # 클라이언트에는 일반화된 메시지 전달
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "서버 오류로 트윗을 가져오지 못했습니다."},
        )

@router.post("/reply/auto_generate", status_code=status.HTTP_200_OK)
async def auto_generate_reply(
    request: AutoReplyRequest,
    llm: LLMService = Depends(get_llm_service),
):
    """트윗 내용에 기반하여 자동 리플라이 메시지를 생성합니다."""
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
    db: AsyncSession = Depends(get_db_session),
    llm: LLMService = Depends(get_llm_service),
):
    """지정된 트윗에 리플라이를 전송합니다."""
    service = TwitterService(db, llm)
    try:
        return await service.send_reply(tweet_id, request.tweet_text)
    except Exception:
        logger.exception(f"리플라이 전송 중 오류: tweet_id={tweet_id}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "리플라이 전송에 실패했습니다."},
        )