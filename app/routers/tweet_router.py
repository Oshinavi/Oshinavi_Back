import logging
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tweet import AutoReplyRequest, SendReplyRequest
from app.core.database import get_db_session
from app.services.twitter.tweet_service import TweetService

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tweets", tags=["Tweet"])


@router.get("/{screen_name}", status_code=status.HTTP_200_OK)
async def fetch_user_tweets(
    screen_name: str,
    db: AsyncSession = Depends(get_db_session),
):
    """특정 유저의 최신 트윗을 수집하고 저장합니다."""
    service = TweetService(db)
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
    db: AsyncSession = Depends(get_db_session),
):
    """트윗 내용에 기반하여 자동 리플라이 메시지를 생성합니다."""
    service = TweetService(db)
    try:
        reply = await service.generate_auto_reply(request.tweet_text)
        return {"reply": reply}
    except Exception:
        logger.exception("자동 리플라이 생성 중 오류 발생")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "자동 리플라이 생성에 실패했습니다."},
        )


@router.post("/reply/{tweet_id}", status_code=status.HTTP_200_OK)
async def send_reply(
    tweet_id: int,  # 숫자 ID로 받습니다
    request: SendReplyRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """지정된 트윗에 리플라이를 전송합니다."""
    service = TweetService(db)
    try:
        result = await service.send_reply(tweet_id, request.tweet_text)
        return result
    except Exception:
        logger.exception(f"리플라이 전송 중 오류: tweet_id={tweet_id}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "리플라이 전송에 실패했습니다."},
        )