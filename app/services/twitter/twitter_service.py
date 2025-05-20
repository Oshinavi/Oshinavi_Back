# app/services/twitter/twitter_service.py

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Union, Optional, List, Tuple

import asyncio
from sqlalchemy.exc import IntegrityError
from selenium.common.exceptions import TimeoutException

from app.models import ReplyLog
from app.models.post import Post
from app.repositories.tweet_repository import TweetRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.services.llm.llm_service import LLMService
from app.schemas.llm_schema import TranslationResult
from app.utils.tco_resolver import TcoResolver
from app.utils.exceptions import NotFoundError
from twikit.errors import NotFound as TwikitNotFound

logger = logging.getLogger(__name__)


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


def _format_dt(dt: Union[str, datetime]) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt


class TwitterService:
    def __init__(self, db, llm_service: LLMService, user_internal_id: str):
        self.repo           = TweetRepository(db)
        self.llm            = llm_service
        self.twitter_client = TwitterClientService(user_internal_id)
        self.twitter_user   = TwitterUserService(self.twitter_client)
        self.resolver       = TcoResolver()

    async def _extract_image_urls(self, media_entries: list) -> List[str]:
        raw_urls = []
        for m in media_entries or []:
            if getattr(m, "type", None) != "photo":
                continue
            url = getattr(m, "media_url_https", None) or getattr(m, "url", None)
            if url:
                raw_urls.append(url)

        resolved = []
        for url in raw_urls:
            try:
                imgs = await self.resolver.resolve([url])
            except TimeoutException:
                logger.warning("이미지 추출 타임아웃, 건너뜀: %s", url)
                continue
            except Exception as e:
                logger.error("미디어 URL 처리 오류 %s: %s", url, e, exc_info=True)
                continue

            if imgs:
                resolved.extend(imgs)
        return resolved

    ### A) remote sync: 트위터에서 새 덩어리 스크랩 → DB 저장, next_remote_cursor 반환
    async def sync_latest_tweets(
        self,
        screen_name: str,
        remote_cursor: Optional[str] = None,
        batch_size: int = 20
    ) -> str:
        # 1) 로그인 + 유저 조회
        await self.twitter_client.ensure_login()
        user = await self.twitter_user.get_user_info(screen_name)
        if not user:
            raise NotFoundError(f"User '{screen_name}' not found")
        author_id = str(user["id"])
        client    = self.twitter_client.get_client()


        # 2) Twikit 으로 스크랩
        tweets = await client.get_user_tweets(
            user_id=author_id,
            tweet_type="Tweets",
            count=batch_size,
            cursor=remote_cursor,
        )
        next_remote = getattr(tweets, "next_cursor", None)

        # 3) DB에 신규만 저장
        existing_ids = await self.repo.list_tweet_ids()
        new_posts = []
        for t in tweets:
            tid = int(t.id)
            if tid in existing_ids:
                continue
            # LLM 번역
            text     = t.full_text
            date_str = _format_dt(t.created_at)
            try:
                tr = await self.llm.translate(text, date_str)
                logger.info(
                    "LLM 번역 결과 ▶ tweet_id=%s\n"
                    "  translated: %s\n"
                    "  category:   %s\n"
                    "  start:      %s\n"
                    "  end:        %s",
                    tid,
                    tr.translated,
                    tr.category,
                    tr.start,
                    tr.end,
                )
            except Exception as e:
            # 에러 로그를 남기고, 원문 fallback
                logger.exception("LLM 번역 중 오류, tweet_id=%s", tid)
                tr = TranslationResult(translated=text, category="일반", start=None, end=None)

            # 이미지 추출
            imgs = await self._extract_image_urls(t.media)
            tweet_date = _parse_any_datetime(t.created_at)

            post = Post(
                tweet_id                  = tid,
                author_internal_id        = author_id,
                tweet_date                = tweet_date,
                tweet_included_start_date = _parse_any_datetime(tr.start),
                tweet_included_end_date   = _parse_any_datetime(tr.end),
                tweet_text                = text,
                tweet_translated_text     = tr.translated,
                tweet_about               = tr.category,
                image_urls                = json.dumps(imgs),
            )
            self.repo.add_post(post)
            new_posts.append(post)

        if new_posts:
            try:
                await self.repo.commit()
            except IntegrityError:
                await self.repo.rollback()
                logger.warning("중복 엔트리 충돌, 롤백")

        return next_remote

    ### B) DB list: keyset-pagination 으로 DB 에 저장된 Post 페이징해서 반환
    async def list_saved_tweets(
        self,
        screen_name: str,
        count: int = 20,
        db_cursor: Optional[str] = None
    ) -> Tuple[List[dict], Optional[str]]:
        user = await self.twitter_user.get_user_info(screen_name)
        profile_image_url = user.get("profile_image_url") if user else None


        # parse db_cursor: "iso_datetime|tweet_id" base64-url-safe
        last_date = last_id = None
        if db_cursor:
            import base64
            raw = base64.urlsafe_b64decode(db_cursor.encode()).decode()
            dt_str, id_str = raw.split("|", 1)
            last_date = datetime.fromisoformat(dt_str)
            last_id   = int(id_str)

        # TweetRepository 의 keyset 메서드 호출
        posts = await self.repo.list_posts_by_cursor(
            twitter_id=screen_name,
            limit=count,
            last_date=last_date,
            last_id=last_id,
        )

        serialized = []
        for p in posts:
            serialized.append({
                "tweet_userid": p.author.twitter_id,
                "tweet_id":     p.tweet_id,
                "tweet_username": p.author.username,
                "tweet_date":   p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_text":   p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about":  p.tweet_about,
                "tweet_included_start_date": (
                    p.tweet_included_start_date.strftime("%Y-%m-%d %H:%M:%S")
                    if p.tweet_included_start_date else None
                ),
                "tweet_included_end_date": (
                    p.tweet_included_end_date.strftime("%Y-%m-%d %H:%M:%S")
                    if p.tweet_included_end_date else None
                ),
                "image_urls": json.loads(p.image_urls) if p.image_urls else [],
                "profile_image_url": profile_image_url,
            })

        # 다음 cursor 생성
        if posts:
            last = posts[-1]
            tok = f"{last.tweet_date.isoformat()}|{last.tweet_id}"
            import base64
            next_db = base64.urlsafe_b64encode(tok.encode()).decode()
        else:
            next_db = None

        return serialized, next_db

    async def classify_and_schedule(
            self, tweet_id: int
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        1) DB에서 해당 tweet_id의 Post 조회
        2) 이미 분류·일정이 설정되어 있으면 바로 반환
        3) 그렇지 않으면, LLMService.classify, .extract_schedule 호출
           → DB 업데이트 후 결과 반환
        """
        post = await self.repo.get_post_by_tweet_id(tweet_id)
        if not post:
            raise NotFoundError(f"Tweet {tweet_id} not found")

        # 이미 한 번 처리된 경우
        if post.schedule_checked:
            return (
                post.tweet_about,
                post.tweet_included_start_date.strftime("%Y-%m-%d %H:%M:%S")
                if post.tweet_included_start_date else None,
                post.tweet_included_end_date.strftime("%Y-%m-%d %H:%M:%S")
                if post.tweet_included_end_date else None,
                post.schedule_title,
                post.schedule_description,
            )

        # ── LLM으로 새로 분류·일정 추출 ─────────────────────────────
        base_text = post.tweet_text
        date_str = post.tweet_date.strftime("%Y-%m-%d %H:%M:%S")

        # 1) 분류
        category, class_title, class_desc = await self.llm.classify(base_text)
        logger.info(
            "LLM 분류 결과 ▶ tweet_id=%s  category=%s  title=%s  desc=%s",
            tweet_id,
            category,
            class_title,
            class_desc,
        )

        # 2) 스케줄 원시 추출 (to_thread로 sync 호출, timestamp 추가)
        raw = await asyncio.to_thread(
            self.llm.pipeline.sched_chain.run,
            base_text,
            date_str
        )
        first_line = raw.strip().splitlines()[0]
        if not re.match(
                r'^(?:\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}|None) ␞ (?:\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}|None)$',
                first_line):
            first_line = "None ␞ None"

        raw = first_line
        logger.info(
            "LLM 스케줄 원시 결과(후처리) ▶ tweet_id=%s  raw=\"%s\"",
            tweet_id,
            raw.replace("\n", "\\n")
        )

        # 3) 파싱된 시작/종료
        start, end = [s.strip() for s in raw.split("␞", 1)]
        logger.info(
            "LLM 스케줄 파싱 결과 ▶ tweet_id=%s  start=%s  end=%s",
            tweet_id, start, end
        )

        # 4) DB에 업데이트
        post.tweet_about = category
        post.tweet_included_start_date = _parse_any_datetime(start)
        post.tweet_included_end_date = _parse_any_datetime(end)
        post.schedule_title = class_title
        post.schedule_description = class_desc
        post.schedule_checked = True
        self.repo.add_post(post)
        await self.repo.commit()

        return category, start or None, end or None, class_title, class_desc

    async def fetch_replies(
            self,
            tweet_id: int,
            cursor: int = 0,
            count: int = 20,
    ) -> List[dict]:
        """
        주어진 tweet_id 에 달린 리플들을 offset(cursor) 기반으로 페이징하여 반환
        - cursor: 리스트 시작 인덱스
        - count: 가져올 개수
        """
        # 1) 로그인 보장
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        # 2) 트윗 객체 가져오기
        tweet = await client.get_tweet_by_id(str(tweet_id))
        if not tweet:
            raise NotFoundError(f"Tweet {tweet_id} not found")

        # 3) .replies 리스트에서 cursor/count 만큼 슬라이스
        raw = getattr(tweet, "replies", []) or []
        page = raw[cursor: cursor + count]

        # 4) @screen_name 제거하고 필요한 필드만 추출
        out: List[dict] = []
        for r in page:
            # 트윗 텍스트 맨 앞의 멘션(@아이디) 제거
            text = re.sub(r'^@\w+\s*', '', r.full_text or '')
            out.append({
                "id": int(r.id),
                "screen_name": r.user.screen_name,
                "user_name": r.user.name,
                "text": text,
                "profile_image_url": getattr(r.user, "profile_image_url_https", None)
                                     or getattr(r.user, "profile_image_url", None),
                "created_at": getattr(r, "created_at", None),
                "is_mine": str(r.user.id) == self.twitter_client.user_id,
            })

        return out

    async def send_reply(self, tweet_id: int, tweet_text: str) -> dict:
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        tweet = await client.get_tweet_by_id(str(tweet_id))
        if not tweet:
            raise NotFoundError("해당 트윗이 존재하지 않습니다.")

        # 1) 답글 생성
        result = await client.create_tweet(text=tweet_text, reply_to=str(tweet_id))

        # 2) DB에 로그 남기기
        log    = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        await self.repo.commit()

        # 3) Twikit Tweet 객체 → 프론트에 일관된 형식(dict)으로 변환
        reply_dict = {
            "id": int(result.id),
            "screen_name": result.user.screen_name,
            "user_name": result.user.name,
            "text": result.full_text,
            "profile_image_url": (
                getattr(result.user, "profile_image_url_https", None)
                or getattr(result.user, "profile_image_url", None)
            ),
            "created_at": result.created_at,
            "is_mine": True
        }
        return reply_dict

    async def delete_reply(self, reply_id: int) -> None:
        """
        주어진 reply_id(트윗 ID)에 해당하는 트윗(리플라이)을 삭제합니다.
        """
        # 1) 로그인 보장
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        # 2) 삭제 호출
        try:
            await client.delete_tweet(str(reply_id))
        except TwikitNotFound:
            # twikit에서 못 찾으면 우리의 NotFoundError로 변환
            raise NotFoundError(f"Reply {reply_id} not found")

        # DB 로그에서도 삭제
        await self.repo.delete_reply_log(reply_id)