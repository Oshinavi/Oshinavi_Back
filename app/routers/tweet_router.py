# app/routers/tweet_router.py

import logging
from typing import Dict, Optional, Union, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.schemas.llm_schema import ReplyResult
from app.schemas.tweet_schema import (
    AutoReplyRequest,
    SendReplyRequest,
    TweetPageResponse,
    TweetMetadataResponse, ReplyResponse,
)
from app.dependencies import get_llm_service, get_twitter_service
from app.services.twitter.twitter_service import TwitterService
from app.services.llm.llm_service import LLMService
from app.utils.exceptions import NotFoundError
from twikit.errors import DuplicateTweet as TwikitDuplicateTweet
from fastapi import Response
from twikit.errors import NotFound as TwikitNotFound

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

@router.get(
    "/{tweet_id}/metadata",
    response_model=TweetMetadataResponse,
    status_code=status.HTTP_200_OK,
)
async def get_tweet_metadata(
    tweet_id: int,
    twitter_service: TwitterService = Depends(get_twitter_service),
) -> TweetMetadataResponse:
     """
     클라이언트가 분류·일정 정보가 필요할 때 호출합니다.
     1) DB에 이미 분류·일정이 등록되어 있으면 그대로 반환
     2) 없으면 LLMService로 처리 → DB 업데이트 후 반환
     """
     try:
         category, start, end, title, desc = await twitter_service.classify_and_schedule(tweet_id)
         return TweetMetadataResponse(
             category=category,
             start=start,
             end=end,
             schedule_title=title,
             schedule_description=desc,
         )
     except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
     except Exception:
        logger.exception("[get_tweet_metadata] 오류, tweet_id=%s", tweet_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="분류·일정 정보를 가져오지 못했습니다."
        )

@router.get(
    "/{tweet_id}/replies",
    response_model=List[ReplyResponse],
    status_code=status.HTTP_200_OK,
    summary="특정 트윗의 리플(답글) 목록 조회"
)
async def get_tweet_replies(
    tweet_id: int,
    twitter_service: TwitterService = Depends(get_twitter_service),
) -> List[ReplyResponse]:
    """
    1) TwitterService.fetch_replies 로 실제 리플을 가져오고,
    2) Pydantic ReplyResponse 리스트로 반환합니다.
    """
    try:
        raw = await twitter_service.fetch_replies(tweet_id)
        # Pydantic 으로 자동 변환
        return [ReplyResponse(**r) for r in raw]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("[get_tweet_replies] 오류, tweet_id=%s", tweet_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리플을 가져오는 중 오류가 발생했습니다."
        )

@router.post(
    "/{tweet_id}/reply/auto_generate",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str]
)
async def auto_generate_reply(
    tweet_id: int,
    req: AutoReplyRequest,
    twitter_service: TwitterService = Depends(get_twitter_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> Dict[str, str]:
    """
    트윗에 달린 리플들 중 두 번째를 제외한 나머지를
    LLM 컨텍스트로 넘겨 자동 리플라이를 생성합니다.
    """
    try:
        # 1) 해당 트윗의 리플 조회
        raw_replies = await twitter_service.fetch_replies(tweet_id)
        # 2) 2번째(인덱스 1) 제외
        contexts = [r["text"] for i, r in enumerate(raw_replies) if i != 1]
        formatted = "\n".join(f"- {c}" for c in contexts)
        # 3) LLM 호출
        result: ReplyResult = await llm_service.reply(req.tweet_text, contexts)
        return {"reply": result.reply_text}
    except NotFoundError as e:
        # 트윗이나 리플을 못 찾았을 때
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("[auto_generate_reply] 오류, tweet_id=%s", tweet_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="자동 리플라이 생성에 실패했습니다."
        )


@router.post(
    "/reply/{tweet_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReplyResponse,
    summary="해당 트윗에 답글 보내기"
)
async def send_reply(
    tweet_id: int,
    req: SendReplyRequest,
    twitter_service: TwitterService = Depends(get_twitter_service),
) -> ReplyResponse:
    """
    1) client.create_tweet 으로 답글 생성
    2) DB에 로그 저장
    3) 생성된 답글(Tweet)을 ReplyResponse 로 반환
    """
    try:
        reply_dict = await twitter_service.send_reply(tweet_id, req.tweet_text)
        return ReplyResponse(**reply_dict)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TwikitDuplicateTweet:
        # 중복된 내용으로 트윗을 보내면 발생하는 오류
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="중복된 리플라이입니다."
        )
    except Exception:
        logger.exception("[send_reply] 리플라이 전송 중 오류: %s", tweet_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="리플라이 전송 실패"
        )

@router.delete(
    "/reply/{reply_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내가 보낸 리플라이 삭제"
)
async def delete_reply(
    reply_id: int,
    twitter_service: TwitterService = Depends(get_twitter_service),
) -> Response:
    """
    1) twikit.delete_tweet 으로 트윗(리플라이) 삭제
    2) DB 로그(ReplyLog)에서도 제거
    3) 204 No Content 반환
    """
    try:
        await twitter_service.delete_reply(reply_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("[delete_reply] 오류, reply_id=%s", reply_id)
        raise HTTPException(
            status_code=500,
            detail="리플라이 삭제에 실패했습니다."
        )