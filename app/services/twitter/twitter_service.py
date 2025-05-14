import logging
from datetime import datetime, timedelta
from typing import Union, Optional
from sqlalchemy.exc import IntegrityError

from app.models import ReplyLog
from app.repositories.tweet_repository import TweetRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.user_service import TwitterUserService
from app.services.llm.llm_service import LLMService
from app.schemas.llm_schema import TranslationResult
from app.models.post import Post
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class TwitterService:
    def __init__(
        self,
        db,
        llm_service: LLMService,
        user_internal_id: str,   # 이제 필수 인자
    ):
        # DB 저장소, LLM, 그리고 사용자별 트위터 클라이언트 초기화
        self.repo           = TweetRepository(db)
        self.twitter_client = TwitterClientService(user_internal_id)
        self.twitter_user   = TwitterUserService(self.twitter_client)
        self.llm            = llm_service

    async def fetch_and_store_latest_tweets(self, screen_name: str) -> list[dict]:
        # 1) 쿠키 기반 로그인 복원
        await self.twitter_client.ensure_login()

        # 2) 대상 사용자 정보 조회
        user = await self.twitter_user.get_user_info(screen_name)
        if not user:
            raise NotFoundError(f"User '{screen_name}' not found")

        author_id = str(user['id'])
        profile_image_url = user.get('profile_image_url')
        client = self.twitter_client.get_client()

        # 3) 트윗 가져오기
        tweets = await client.get_user_tweets(user_id=author_id, tweet_type='Tweets', count=50)

        existing = set(await self.repo.list_tweet_ids())
        new_posts = []

        for t in tweets:
            tid = str(t.id)
            if tid in existing:
                continue

            logger.info("[TwitterService] ▶ 원본 트윗 (%s):\n%s", tid, t.full_text)

            # 날짜 파싱
            tweet_date = _parse_any_datetime(t.created_at)
            if not tweet_date:
                logger.warning("[TwitterService] 날짜 파싱 실패: %s", t.created_at)
                continue

            # LLM으로 번역
            try:
                tr: TranslationResult = await self.llm.translate(
                    t.full_text, tweet_date.strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception as e:
                logger.error("[TwitterService] LLM 번역 실패: %s", e, exc_info=True)
                tr = TranslationResult(
                    translated=t.full_text,
                    category="일반",
                    start=None,
                    end=None,
                )

            logger.info(
                "[TwitterService] ▶ LLM 응답 (%s): 번역=%s, 분류=%s, 시작=%s, 종료=%s",
                tid, tr.translated, tr.category, tr.start, tr.end
            )

            start_dt = _parse_any_datetime(tr.start)
            end_dt   = _parse_any_datetime(tr.end)

            # DB에 저장할 Post 객체 생성
            post = Post(
                tweet_id                  = int(t.id),
                author_internal_id        = author_id,
                tweet_date                = tweet_date,
                tweet_included_start_date = start_dt,
                tweet_included_end_date   = end_dt,
                tweet_text                = t.full_text,
                tweet_translated_text     = tr.translated,
                tweet_about               = tr.category,
            )
            self.repo.add_post(post)
            new_posts.append(post)

        # 4) 새로 추가된 포스트 커밋
        if new_posts:
            try:
                await self.repo.commit()
            except IntegrityError:
                logger.warning("[TwitterService] 중복 엔트리 스킵")
                await self.repo.rollback()
            except Exception as e:
                logger.error("[TwitterService] DB 커밋 오류: %s", e, exc_info=True)
                await self.repo.rollback()
                raise

        # 5) 저장된 게시물 리스트 반환
        posts = await self.repo.list_by_username(screen_name)
        return [
            {
                "tweet_id": p.tweet_id,
                "tweet_userid": p.author.twitter_id,
                "tweet_username": p.author.username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_included_start_date": p.tweet_included_start_date and p.tweet_included_start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_included_end_date":   p.tweet_included_end_date   and p.tweet_included_end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about": p.tweet_about,
                "profile_image_url": profile_image_url,
            }
            for p in posts
        ]

    async def send_reply(self, tweet_id: int, tweet_text: str) -> dict:
        # 1) 쿠키 기반 로그인 복원
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        # 2) 리플라이 대상 트윗 존재 확인
        tweet = await client.get_tweet_by_id(str(tweet_id))
        if not tweet:
            raise NotFoundError("해당 트윗이 존재하지 않습니다.")

        # 3) 리플라이 전송
        result = await client.create_tweet(
            text= tweet_text,
            reply_to = str(tweet_id)
        )

        # 4) 전송 로그 DB 저장
        log = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        await self.repo.commit()

        return {
            "reply_tweet_id": str(result.id),
            "created_at": result.created_at,
            "text": result.text,
        }


# ─── 헬퍼 함수 ───────────────────────────────────────────────

def _parse_any_datetime(
    dt: Union[str, datetime, None]
) -> Optional[datetime]:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt

    s = dt.strip()
    try:
        utc = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
        return utc + timedelta(hours=9)
    except Exception:
        pass

    try:
        return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"[TwitterService] 날짜 파싱 실패(LLM 포맷): '{s}' → {e}")
        return None