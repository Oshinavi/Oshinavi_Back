# app/routers/tweet_router.py

import logging
from typing import Dict, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.schemas.llm_schema import ReplyResult
from app.schemas.tweet_schema import (
    AutoReplyRequest,
    SendReplyRequest,
    TweetPageResponse,
    TweetResponse,
)
from app.dependencies import get_llm_service, get_twitter_service
from app.services.twitter.twitter_service import TwitterService
from app.services.llm.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tweets", tags=["Tweet"])


@router.get(
    "/{screen_name}",
    response_model=TweetPageResponse,
    status_code=status.HTTP_200_OK,
)
async def fetch_user_tweets(
    screen_name: str,
    # 트위터 원격 스크랩용 커서
    remote_cursor: Optional[str] = Query(
        None, description="트위터에서 추가 스크랩할 때 쓸 cursor"
    ),
    # DB keyset pagination 커서
    db_cursor: Optional[str] = Query(
        None, description="DB에서 추가 페이지 조회할 때 쓸 cursor"
    ),
    count: int = Query(20, ge=1, le=100),
    svc: TwitterService = Depends(get_twitter_service),
) -> Union[Dict[str, Union[list, None]], JSONResponse]:
    """
    1) remote_cursor 로 트위터에서 batch_size 개를 스크랩(sync_latest_tweets)
    2) 그 결과 신규 저장 → next_remote_cursor 반환
    3) db_cursor + count 로 DB에서 먼저 page 만큼 뽑아 list_saved_tweets
    4) next_db_cursor 반환
    """
    try:
        # A) twitter 웹에서 한 덩어리 스크랩 & 저장 → 다음 remote cursor
        next_remote = await svc.sync_latest_tweets(
            screen_name, remote_cursor, batch_size=count
        )

        # B) DB에서 keyset-pagination 로 꺼내서 직렬화 → 다음 db cursor
        tweets, next_db = await svc.list_saved_tweets(
            screen_name, count=count, db_cursor=db_cursor
        )

        return {
            "tweets": tweets,
            # 클라이언트 쪽에 두 개를 모두 넘겨 줍니다.
            "next_remote_cursor": next_remote,
            "next_db_cursor":     next_db,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("[fetch_user_tweets] 트윗 조회 중 오류 발생: %s", screen_name)
        return JSONResponse(
            {"error": "서버 오류로 트윗을 가져오지 못했습니다."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@router.post(
    "/reply/auto_generate",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str]
)
async def auto_generate_reply(
    req: AutoReplyRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> Union[Dict[str, str], JSONResponse]:
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


@router.post(
    "/reply/{tweet_id}",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str]
)
async def send_reply(
    tweet_id: int,
    req: SendReplyRequest,
    twitter_service: TwitterService = Depends(get_twitter_service),
) -> Union[Dict[str, str], JSONResponse]:
    """
    TwitterService를 통해 특정 트윗(tweet_id)에 리플라이를 전송합니다.
    1) 로그인 유저 레코드 조회
    2) TwitterService 생성
    3) 리플라이 전송 실행
    """
    try:
        result = await twitter_service.send_reply(tweet_id, req.tweet_text)
        return {
            "reply_tweet_id": result["reply_tweet_id"],
            "text":           result["text"],
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("[send_reply] 리플라이 전송 중 오류: %s", tweet_id)
        return JSONResponse(
            content={"error": "리플라이 전송 실패"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )