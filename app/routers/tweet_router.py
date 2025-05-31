import logging
from typing import Dict, Optional, Union, List

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from twikit.errors import DuplicateTweet as TwikitDuplicateTweet

from app.dependencies import get_llm_service, get_twitter_service
from app.schemas.llm_schema import ReplyResult
from app.schemas.tweet_schema import (
    AutoReplyRequest,
    SendReplyRequest,
    TweetPageResponse,
    TweetMetadataResponse,
    ReplyResponse,
)
from app.services.twitter.twitter_service import TwitterService
from app.services.llm.llm_service import LLMService
from app.utils.exceptions import ConflictError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tweets", tags=["Tweet"])

@router.get("/{screen_name}", response_model=TweetPageResponse)
async def fetch_user_tweets(
    screen_name: str,
    remote_cursor: Optional[str] = Query(None, description="트위터에서 추가 스크랩할 때 사용할 cursor"),
    db_cursor: Optional[str] = Query(None, description="DB에서 추가 페이지 조회할 때 사용할 cursor"),
    count: int = Query(20, ge=1, le=100),
    svc: TwitterService = Depends(get_twitter_service),
) -> Dict[str, Union[list, None]]:
    """
    1) remote_cursor로 트위터에서 batch_size 개를 스크랩(sync_latest_tweets)
    2) 신규 저장 후 next_remote_cursor 반환
    3) db_cursor+count로 DB에서 페이지 조회(list_saved_tweets)
    4) next_db_cursor 반환
    """
    next_remote = await svc.sync_latest_tweets(screen_name, remote_cursor, batch_size=count)
    tweets, next_db = await svc.list_saved_tweets(screen_name, count=count, db_cursor=db_cursor)
    return {"tweets": tweets, "next_remote_cursor": next_remote, "next_db_cursor": next_db}

@router.get("/{tweet_id}/metadata", response_model=TweetMetadataResponse)
async def get_tweet_metadata(
    tweet_id: int,
    svc: TwitterService = Depends(get_twitter_service),
) -> TweetMetadataResponse:
    """
    1) DB에 분류·일정 정보가 있으면 반환
    2) 없으면 LLMService 처리 → DB 업데이트 후 반환
    """
    category, start, end, title, desc = await svc.classify_and_schedule(tweet_id)
    return TweetMetadataResponse(
        category=category,
        start=start,
        end=end,
        schedule_title=title,
        schedule_description=desc,
    )

@router.get("/{tweet_id}/replies", response_model=List[ReplyResponse], summary="특정 트윗의 리플 목록 조회")
async def get_tweet_replies(
    tweet_id: int,
    svc: TwitterService = Depends(get_twitter_service),
) -> List[ReplyResponse]:
    """
    1) TwitterService.fetch_replies로 리플 조회
    2) ReplyResponse 리스트로 반환
    """
    raw = await svc.fetch_replies(tweet_id)
    return [ReplyResponse(**r) for r in raw]

@router.post("/{tweet_id}/reply/auto_generate", response_model=Dict[str, str])
async def auto_generate_reply(
    tweet_id: int,
    req: AutoReplyRequest,
    twitter_svc: TwitterService = Depends(get_twitter_service),
    llm_svc: LLMService = Depends(get_llm_service),
) -> Dict[str, str]:
    """
    트윗 리플 중 두 번째를 제외한 텍스트로 LLM에 전달하여 자동 리플라이 생성
    """
    raw = await twitter_svc.fetch_replies(tweet_id)
    contexts = [r["text"] for i, r in enumerate(raw) if i != 1]
    result: ReplyResult = await llm_svc.reply(req.tweet_text, contexts)
    return {"reply": result.reply_text}

@router.post("/reply/{tweet_id}", response_model=ReplyResponse, summary="해당 트윗에 답글 보내기")
async def send_reply(
    tweet_id: int,
    req: SendReplyRequest,
    svc: TwitterService = Depends(get_twitter_service),
) -> ReplyResponse:
    """
    1) TwitterService.send_reply로 답글 생성
    2) DB 로그 저장
    3) ReplyResponse 반환
    """
    try:
        data = await svc.send_reply(tweet_id, req.tweet_text)
        return ReplyResponse(**data)
    except TwikitDuplicateTweet:
        raise ConflictError("중복된 리플라이입니다.")

@router.delete("/reply/{reply_id}", status_code=status.HTTP_204_NO_CONTENT, summary="내가 보낸 리플라이 삭제")
async def delete_reply(
    reply_id: int,
    svc: TwitterService = Depends(get_twitter_service),
) -> Response:
    """
    1) TwitterService.delete_reply로 리플라이 삭제
    2) DB 로그 제거
    3) 204 No Content 반환
    """
    await svc.delete_reply(reply_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
