import json
import logging
from datetime import datetime, timedelta
from typing import Union, Optional

from sqlalchemy.exc import IntegrityError

from app.models.reply_log import ReplyLog
from app.models.post import Post
from app.repositories.tweet_repository import TweetRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.services.llm.llm_service import LLMService
from app.schemas.llm_schema import TranslationResult
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)

class TwitterService:
    """
    Twikit 기반의 트위터 서비스 클래스
    - 최신 트윗 저장
    - 특정 트윗에 대한 리플라이 전송
    """
    def __init__(
        self,
        db,
        llm_service: LLMService,
        user_internal_id: str,   # Twikit 클라이언트용 내부 사용자 ID
    ):
        """
        - db: 데이터베이스 세션
        - llm_service: 번역 및 분류용 LLM 서비스
        - user_internal_id: Twikit 클라이언트 쿠키 식별자
        """
        self.repo = TweetRepository(db)
        self.twitter_client = TwitterClientService(user_internal_id)
        self.twitter_user = TwitterUserService(self.twitter_client)
        self.llm = llm_service

    async def fetch_and_store_latest_tweets(self, screen_name: str) -> list[dict]:
        """
        특정 사용자(screen_name)의 최신 트윗을 가져와 DB에 저장
        저장된 게시물 정보를 dict 리스트로 반환
        """

        # 1) Twikit 로그인 상태 보장
        await self.twitter_client.ensure_login()

        # 2) 해당 트위터 사용자 정보 조회
        user = await self.twitter_user.get_user_info(screen_name)
        if not user:
            # 유저 없으면 error raise
            raise NotFoundError(f"User '{screen_name}' not found")

        author_id = str(user['id'])
        profile_image_url = user.get('profile_image_url')
        client = self.twitter_client.get_client()

        # 3) 최대 50개의 트윗 가져오기
        tweets = await client.get_user_tweets(
            user_id=author_id,
            tweet_type='Tweets',
            count=50
        )

        # 이미 저장된 트윗 ID 집합 조회
        existing = set(await self.repo.list_tweet_ids())
        new_posts = []

        for t in tweets:
            tid = str(t.id)
            if tid in existing:
                # 중복 트윗은 스킵
                continue
            # 이미지 URL 추출 (media 속성이 있다면)
            media_urls = []
            if getattr(t, "media", None):
                for m in t.media:  # Twikit Tweet.media 리스트
                    if getattr(m, "url", None):
                        media_urls.append(m.url)
                    elif getattr(m, "media_url_https", None):
                        media_urls.append(m.media_url_https)

            logger.info("[TwitterService] ▶ 원본 트윗 (%s):\n%s", tid, t.full_text)

            # 트윗 생성일 파싱 (한국 시간 기준으로)
            tweet_date = _parse_any_datetime(t.created_at)
            if not tweet_date:
                logger.warning("[TwitterService] 날짜 파싱 실패: %s", t.created_at)
                continue

            # 4) LLM 번역 및 분류 수행
            try:
                tr: TranslationResult = await self.llm.translate(
                    t.full_text, tweet_date.strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception as e:
                # LLM 실패 시 예외 처리 후 기본값 사용
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

            # LLM이 반환한 시작/종료 시간 파싱
            start_dt = _parse_any_datetime(tr.start)
            end_dt   = _parse_any_datetime(tr.end)

            # Post 모델 인스턴스 생성
            post = Post(
                tweet_id                  = int(t.id),
                author_internal_id        = author_id,
                tweet_date                = tweet_date,
                tweet_included_start_date = start_dt,
                tweet_included_end_date   = end_dt,
                tweet_text                = t.full_text,
                tweet_translated_text     = tr.translated,
                tweet_about               = tr.category,
                image_urls                = json.dumps(media_urls) if media_urls else None,  # JSON 직렬화
            )
            # DB 세션에 추가
            self.repo.add_post(post)
            new_posts.append(post)

        # 5) 새 포스트가 있다면 커밋
        if new_posts:
            try:
                await self.repo.commit()
            except IntegrityError:
                # 중복 엔트리 충돌 발생 시 롤백
                logger.warning("[TwitterService] 중복 엔트리 스킵")
                await self.repo.rollback()
            except Exception as e:
                # 기타 DB 에러 시 롤백 후 재발생
                logger.error("[TwitterService] DB 커밋 오류: %s", e, exc_info=True)
                await self.repo.rollback()
                raise

        # 6) 저장된 게시물 조회 후 출력 포맷 변환
        posts = await self.repo.list_posts_by_username(screen_name)
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
                "image_urls": json.loads(p.image_urls) if p.image_urls else [],
                "profile_image_url": profile_image_url,
            }
            for p in posts
        ]

    async def send_reply(self, tweet_id: int, tweet_text: str) -> dict:
        """
        특정 트윗에 리플라이를 전송하고 전송 정보를 반환
        """

        # 1) 리플라이 전 로그인 상태 확인
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        # 2) 리플라이 대상 트윗 존재 확인
        tweet = await client.get_tweet_by_id(str(tweet_id))
        if not tweet:
            raise NotFoundError("해당 트윗이 존재하지 않습니다.")

        # 3) 리플라이 전송 API 호출
        result = await client.create_tweet(
            text= tweet_text,
            reply_to = str(tweet_id)
        )

        # 4) 전송 로그 모델 생성 및 저장
        log = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        await self.repo.commit()

        # 5) 응답 데이터 반환
        return {
            "reply_tweet_id": str(result.id),
            "created_at": result.created_at,
            "text": result.text,
        }


# ─── 헬퍼 함수 ───────────────────────────────────────────────

def _parse_any_datetime(
    dt: Union[str, datetime, None]
) -> Optional[datetime]:
    """
    문자열 또는 datetime 인자를 파싱하여 datetime 객체로 반환
    - 트윗 API 기본 포맷: "%a %b %d %H:%M:%S %z %Y"
    - LLM 반환 포맷: "%Y.%m.%d %H:%M:%S"
    """
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt

    s = dt.strip()
    try:
        # UTC+0 타임스탬프 파싱 후 한국 시간으로 변환
        utc = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
        return utc + timedelta(hours=9)
    except Exception:
        pass

    try:
        # LLM이 제공하는 포맷 파싱
        return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"[TwitterService] 날짜 파싱 실패(LLM 포맷): '{s}' → {e}")
        return None