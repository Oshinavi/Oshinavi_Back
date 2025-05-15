# app/services/twitter/twitter_service.py

import json
import logging
from datetime import datetime, timedelta
from typing import Union, Optional, List

from sqlalchemy.exc import IntegrityError
from app.models.reply_log import ReplyLog
from app.models.post import Post
from app.repositories.tweet_repository import TweetRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.services.llm.llm_service import LLMService
from app.schemas.llm_schema import TranslationResult
from app.utils.tco_resolver import TcoResolver
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)

class TwitterService:
    """
    최신 트윗 저장 및 리플라이 전송
    """
    def __init__(
        self,
        db,
        llm_service: LLMService,
        user_internal_id: str,
    ):
        self.repo           = TweetRepository(db)
        self.llm            = llm_service
        self.twitter_client = TwitterClientService(user_internal_id)
        self.twitter_user   = TwitterUserService(self.twitter_client)
        self.resolver       = TcoResolver()

    async def _extract_image_urls(self, media_entries: list) -> List[str]:
        """
        twikit media 객체 대신, t.co 링크를 TcoResolver 로 처리
        """
        raw_urls = []
        for m in media_entries or []:
            if getattr(m, "media_url_https", None):
                raw_urls.append(m.media_url_https)
            elif getattr(m, "url", None):
                raw_urls.append(m.url)

        if raw_urls:
            raw_urls = await self.resolver.resolve(raw_urls)
        return await self.resolver.resolve(raw_urls)

    async def fetch_and_store_latest_tweets(self, screen_name: str) -> List[dict]:
        await self.twitter_client.ensure_login()
        user = await self.twitter_user.get_user_info(screen_name)
        if not user:
            raise NotFoundError(f"User '{screen_name}' not found")

        author_id         = str(user["id"])
        profile_image_url = user.get("profile_image_url")
        client            = self.twitter_client.get_client()

        tweets   = await client.get_user_tweets(user_id=author_id, tweet_type="Tweets", count=50)
        existing = set(await self.repo.list_tweet_ids())
        new_posts: List[Post] = []

        for t in tweets:
            tid = str(t.id)
            if tid in existing:
                continue

            logger.info("원본 트윗 (%s): %s", tid, t.full_text)
            media_urls = await self._extract_image_urls(t.media)

            tweet_date = _parse_any_datetime(t.created_at)
            if not tweet_date:
                logger.warning("날짜 파싱 실패: %s", t.created_at)
                continue

            try:
                tr: TranslationResult = await self.llm.translate(
                    t.full_text,
                    tweet_date.strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception as e:
                logger.error("LLM 번역 실패: %s", e, exc_info=True)
                tr = TranslationResult(translated=t.full_text, category="일반", start=None, end=None)

            start_dt = _parse_any_datetime(tr.start)
            end_dt   = _parse_any_datetime(tr.end)
            logger.info("추출된 이미지 URLs for %s: %s", tid, media_urls)

            post = Post(
                tweet_id                  = int(t.id),
                author_internal_id        = author_id,
                tweet_date                = tweet_date,
                tweet_included_start_date = start_dt,
                tweet_included_end_date   = end_dt,
                tweet_text                = t.full_text,
                tweet_translated_text     = tr.translated,
                tweet_about               = tr.category,
                image_urls                = json.dumps(media_urls),
            )
            self.repo.add_post(post)
            new_posts.append(post)

        if new_posts:
            try:
                await self.repo.commit()
            except IntegrityError:
                logger.warning("중복 엔트리 충돌, 롤백")
                await self.repo.rollback()

        posts = await self.repo.list_posts_by_username(screen_name)
        return [
            {
                "tweet_userid": p.author_internal_id,  # 추가
                "tweet_id": p.tweet_id,
                "tweet_username": p.author.username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,  # 추가
                "tweet_about": p.tweet_about,  # 추가
                "tweet_included_start_date": (
                    p.tweet_included_start_date.strftime("%Y-%m-%d %H:%M:%S")
                    if p.tweet_included_start_date else None
                ),  # 추가
                "tweet_included_end_date": (
                    p.tweet_included_end_date.strftime("%Y-%m-%d %H:%M:%S")
                    if p.tweet_included_end_date else None
                ),  # 추가
                "image_urls": json.loads(p.image_urls) if p.image_urls else [],
                "profile_image_url": profile_image_url,
            }
            for p in posts
        ]

    async def send_reply(self, tweet_id: int, tweet_text: str) -> dict:
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        tweet = await client.get_tweet_by_id(str(tweet_id))
        if not tweet:
            raise NotFoundError("해당 트윗이 존재하지 않습니다.")

        result = await client.create_tweet(text=tweet_text, reply_to=str(tweet_id))
        log    = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        await self.repo.commit()

        return {
            "reply_tweet_id": str(result.id),
            "created_at":     result.created_at,
            "text":           result.text,
        }


def _parse_any_datetime(dt: Union[str, datetime, None]) -> Optional[datetime]:
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
    except Exception:
        return None