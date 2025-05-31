# app/services/twitter/twitter_service.py

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Union, Optional, List, Tuple

import asyncio
from sqlalchemy.exc import IntegrityError
from twikit.errors import NotFound as TwikitNotFound

from app.models.post import Post
from app.models.reply_log import ReplyLog
from app.repositories.tweet_repository import TweetRepository
from app.services.twitter.twitter_client_service import TwitterClientService
from app.services.twitter.twitter_user_service import TwitterUserService
from app.services.llm.llm_service import LLMService
from app.schemas.llm_schema import TranslationResult
from app.utils.tco_resolver import TcoResolver
from app.utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _parse_any_datetime(dt: Union[str, datetime, None]) -> Optional[datetime]:
    """
    문자열 또는 datetime을 받아 datetime 객체로 변환
    - Twikit에서 리턴된 str: "%a %b %d %H:%M:%S %z %Y" 또는 "%Y.%m.%d %H:%M:%S" 포맷을 지원
    """
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt
    s = dt.strip()
    try:
        # 예: "Wed Jun 18 12:34:56 +0000 2025"
        utc = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
        return utc + timedelta(hours=9)  # KST 기준으로 변환
    except Exception:
        pass
    try:
        # 예: "2025.06.18 21:34:56"
        return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except Exception:
        return None


def _format_dt(dt: Union[str, datetime]) -> str:
    """
    datetime 또는 문자열(dt)이 들어오면 “YYYY-MM-DD HH:MM:SS” 형태로 반환
    """
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt


class TwitterService:
    """
    트위터-LLM 연동 서비스
    - 트윗 스크래핑 (synchronize_tweets)
    - DB 조회 (list_saved_tweets, fetch_replies, send_reply, etc.)
    - 분류·스케줄 체크 (classify_and_schedule)
    """

    def __init__(self, db, llm_service: LLMService, user_internal_id: str):
        """
        Args:
            db: AsyncSession
            llm_service: LLMService 인스턴스
            user_internal_id: 로그인된 유저의 Twitter 내부 ID (문자열)
        """
        self.repo = TweetRepository(db)
        self.llm = llm_service
        self.twitter_client = TwitterClientService(user_internal_id)
        self.twitter_user = TwitterUserService(self.twitter_client)
        self.resolver = TcoResolver()

    # ────────────────────────────────────────────────────────────────────────────
    async def synchronize_tweets(
        self,
        screen_name: str,
        remote_cursor: Optional[str] = None,
        batch_size: int = 20
    ) -> str:
        """
        1) 로그인 보장 → screen_name → internal_id (Twikit)
        2) Twikit으로부터 최신 트윗 스크랩
        3) DB에 저장되지 않은 신규 트윗만 가공 → Post 리스트 생성
        4) Post 리스트를 DB에 일괄 저장 (commit/rollback 포함)
        5) 다음 remote cursor 반환
        """
        # 1) 로그인 및 사용자 내부 ID 확인
        author_id = await self._ensure_user_logged_in(screen_name)

        # 2) 트윗 스크랩
        tweets, next_remote = await self._fetch_tweets_from_twitter(
            author_id, remote_cursor, batch_size
        )

        if not tweets:
            # 신규 트윗이 없으면, 그냥 이전 cursor 그대로 반환
            return next_remote

        # 3) DB에 저장되지 않은 신규 트윗만 필터링 → Post 객체 생성
        existing_ids = await self.repo.list_tweet_ids()
        new_posts = await self._prepare_posts_for_save(
            tweets, existing_ids, author_id
        )

        # 4) DB 저장
        if new_posts:
            await self._save_posts_batch(new_posts)

        return next_remote

    # ────────────────────────────────────────────────────────────────────────────
    async def _ensure_user_logged_in(self, screen_name: str) -> str:
        """
        Twikit Client로 로그인 보장 후,
        screen_name → internal_id(문자열) 반환
        """
        await self.twitter_client.ensure_login()
        try:
            user_info = await self.twitter_user.get_user_info(screen_name)
        except NotFoundError as e:
            raise NotFoundError(f"User '{screen_name}' not found") from e

        internal_id = str(user_info["id"])
        logger.info(f"[TwitterService] {screen_name} → internal_id={internal_id}")
        return internal_id

    # ────────────────────────────────────────────────────────────────────────────
    async def _fetch_tweets_from_twitter(
        self,
        author_id: str,
        remote_cursor: Optional[str],
        batch_size: int
    ) -> Tuple[List, Optional[str]]:
        """
        Twikit Client를 사용하여 트윗 목록과 다음 cursor 획득
        """
        client = self.twitter_client.get_client()
        try:
            tweets = await client.get_user_tweets(
                user_id=author_id,
                tweet_type="Tweets",
                count=batch_size,
                cursor=remote_cursor,
            )
        except Exception as e:
            logger.error(f"트윗 스크랩 실패 (author_id={author_id}): {e}")
            raise

        # Twikit의 response 객체에 next_cursor 속성이 있음
        next_remote = getattr(tweets, "next_cursor", None)
        return tweets, next_remote

    # ────────────────────────────────────────────────────────────────────────────
    async def _prepare_posts_for_save(
        self,
        tweets,             # Twikit Tweet 객체 리스트
        existing_ids: set,
        author_id: str
    ) -> List[Post]:
        """
        DB에 저장되지 않은 신규 트윗만 골라서,
        1) LLM 번역
        2) 이미지 URL 추출
        3) Post 모델 인스턴스 생성
        """
        new_posts: List[Post] = []

        for t in tweets:
            tid = int(t.id)
            if tid in existing_ids:
                continue

            text = t.full_text
            date_str = _format_dt(t.created_at)

            # (1) LLM 번역
            try:
                tr: TranslationResult = await self.llm.translate(text, date_str)
                logger.info(
                    f"LLM 번역 결과 ▶ tweet_id={tid} "
                    f"translated={tr.translated} category={tr.category} start={tr.start} end={tr.end}"
                )
            except Exception:
                logger.exception("LLM 번역 실패, 원문으로 저장 tweet_id=%s", tid)
                tr = TranslationResult(
                    translated=text, category="일반", start=None, end=None
                )

            # (2) 이미지 URL 추출
            imgs = await self._extract_image_urls(t.media)

            # (3) Post 모델 객체 생성
            tweet_date = _parse_any_datetime(t.created_at)
            post = Post(
                tweet_id=tid,
                author_internal_id=author_id,
                tweet_date=tweet_date,
                tweet_included_start_date=_parse_any_datetime(tr.start),
                tweet_included_end_date=_parse_any_datetime(tr.end),
                tweet_text=text,
                tweet_translated_text=tr.translated,
                tweet_about=tr.category,
                image_urls=json.dumps(imgs),
            )
            new_posts.append(post)

        return new_posts

    # ────────────────────────────────────────────────────────────────────────────
    async def _extract_image_urls(self, media_entries: list) -> List[str]:
        """
        이미지(media) URL을 비동기적으로 실제 큰 이미지 URL로 변환
        (t.co 단축 URL 및 twitter.com/photo 링크를 TcoResolver로 해석)
        """
        raw_urls = []
        for m in media_entries or []:
            # 트윗 media에 type="photo"인 항목만 필터
            if getattr(m, "type", None) != "photo":
                continue
            # `media_url_https` 속성이 있으면 그걸, 아니면 `url` 속성 사용
            url = getattr(m, "media_url_https", None) or getattr(m, "url", None)
            if url:
                raw_urls.append(url)

        resolved = []
        for url in raw_urls:
            # t.co로 단축되었거나, twitter.com/photo 링크면 실제 URL으로 해석
            if "t.co/" in url or "twitter.com/photo" in url:
                try:
                    imgs = await self.resolver.resolve([url])
                    resolved.append(imgs[0] if imgs else url)
                except Exception:
                    logger.warning("이미지 추출 실패, 원본 URL 사용: %s", url)
                    resolved.append(url)
            else:
                resolved.append(url)
        return resolved

    # ────────────────────────────────────────────────────────────────────────────
    async def _save_posts_batch(self, posts: List[Post]) -> None:
        """
        여러 Post 인스턴스를 DB에 일괄 저장
        commit/rollback 처리 모두 이 메소드에서 처리
        """
        try:
            for post in posts:
                self.repo.add_post(post)
            await self.repo.commit()
            logger.info(f"새 트윗 {len(posts)}건 DB 저장 성공")
        except IntegrityError as e:
            await self.repo.rollback()
            logger.warning("DB 저장 중 IntegrityError 발생, 롤백: %s", e)
            # IntegrityError 시 중복 충돌 등으로 새로 저장 실패 → 무시하고 넘어갑니다.

    # ────────────────────────────────────────────────────────────────────────────
    async def list_saved_tweets(
        self,
        screen_name: str,
        count: int = 20,
        db_cursor: Optional[str] = None
    ) -> Tuple[List[dict], Optional[str]]:
        """
        DB에 저장된 트윗을 Keyset Pagination 방식으로 반환
        - screen_name: 트위터 스크린네임
        - count: 가져올 최대 개수
        - db_cursor: “ISO_DATETIME|TWEET_ID” base64-url-safe 형식의 cursor
        Returns:
            (serialized_posts, next_db_cursor)
        """
        # 1) 유저 프로필(이미지 등) 정보 조회
        try:
            user = await self.twitter_user.get_user_info(screen_name)
        except NotFoundError:
            # DB에 저장된 트윗이라도, 만약 screen_name이 틀렸다면 404
            raise NotFoundError(f"User '{screen_name}' not found")

        profile_image_url = user.get("profile_image_url")

        # 2) db_cursor 파싱
        last_date = last_id = None
        if db_cursor:
            import base64
            raw = base64.urlsafe_b64decode(db_cursor.encode()).decode()
            dt_str, id_str = raw.split("|", 1)
            last_date = datetime.fromisoformat(dt_str)
            last_id = int(id_str)

        # 3) TweetRepository를 통해 Post 리스트 조회
        posts = await self.repo.list_posts_by_cursor(
            twitter_id=screen_name,
            limit=count,
            last_date=last_date,
            last_id=last_id
        )

        # 4) 스키마에 맞게 직렬화
        serialized = []
        for p in posts:
            serialized.append({
                "tweet_userid": p.author.twitter_id,
                "tweet_id": p.tweet_id,
                "tweet_username": p.author.username,
                "tweet_date": p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet_text": p.tweet_text,
                "tweet_translated_text": p.tweet_translated_text,
                "tweet_about": p.tweet_about,
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

        # 5) 다음 cursor 생성
        if posts:
            last = posts[-1]
            tok = f"{last.tweet_date.isoformat()}|{last.tweet_id}"
            import base64
            next_db = base64.urlsafe_b64encode(tok.encode()).decode()
        else:
            next_db = None

        return serialized, next_db

    # ────────────────────────────────────────────────────────────────────────────
    async def classify_and_schedule(
        self, tweet_id: int
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        1) DB에서 해당 tweet_id의 Post 조회
        2) 이미 분류·스케줄이 설정되어 있으면 바로 반환
        3) 그렇지 않으면, LLMService.classify, LLMService.extract_schedule 호출
           → DB 업데이트 후 결과 반환
        """
        # 1) Post 조회
        post = await self.repo.get_post_by_tweet_id(tweet_id)
        if not post:
            raise NotFoundError(f"Tweet {tweet_id} not found")

        # 2) 이미 처리된 경우
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

        # 3-1) 분류
        base_text = post.tweet_text
        category, class_title, class_desc = await self.llm.classify(base_text)
        logger.info(
            f"LLM 분류 결과 ▶ tweet_id={tweet_id}  category={category}  title={class_title}  desc={class_desc}"
        )

        # 3-2) 스케줄 원시 추출 (스케줄 체인은 동기 → to_thread로 호출)
        date_str = post.tweet_date.strftime("%Y-%m-%d %H:%M:%S")
        raw_output = await asyncio.to_thread(
            self.llm.pipeline.sched_chain.run, base_text, date_str
        )
        # 첫 줄만 취함
        first_line = raw_output.strip().splitlines()[0]
        # “YYYY.MM.DD HH:MM:SS ␞ YYYY.MM.DD HH:MM:SS” 또는 “None ␞ None” 패턴 검사
        if not re.match(
            r'^(?:\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}|None) ␞ (?:\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}|None)$',
            first_line
        ):
            first_line = "None ␞ None"

        start, end = [s.strip() for s in first_line.split("␞", 1)]
        logger.info(f"LLM 스케줄 파싱 결과 ▶ tweet_id={tweet_id}  start={start}  end={end}")

        # 4) DB 업데이트
        post.tweet_about = category
        post.tweet_included_start_date = _parse_any_datetime(start)
        post.tweet_included_end_date = _parse_any_datetime(end)
        post.schedule_title = class_title
        post.schedule_description = class_desc
        post.schedule_checked = True

        self.repo.add_post(post)
        try:
            await self.repo.commit()
        except Exception as e:
            logger.error(f"분류·스케줄 저장 커밋 실패: {e}")
            await self.repo.rollback()
            raise

        return category, start or None, end or None, class_title, class_desc

    # ────────────────────────────────────────────────────────────────────────────
    async def fetch_replies(
        self,
        tweet_id: int,
        cursor: int = 0,
        count: int = 20,
    ) -> List[dict]:
        """
        주어진 tweet_id에 달린 리플들을 offset(cursor) 기반으로 페이징하여 반환
        - cursor: 시작 인덱스
        - count: 가져올 개수
        """
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        try:
            tweet = await client.get_tweet_by_id(str(tweet_id))
        except TwikitNotFound:
            raise NotFoundError(f"Tweet {tweet_id} not found")
        except Exception as e:
            logger.error(f"Tweet 검색 실패: {e}")
            raise

        if not tweet:
            raise NotFoundError(f"Tweet {tweet_id} not found")

        raw = getattr(tweet, "replies", []) or []
        page = raw[cursor: cursor + count]

        out: List[dict] = []
        for r in page:
            text = re.sub(r'^@\w+\s*', '', r.full_text or '')
            out.append({
                "id": int(r.id),
                "screen_name": r.user.screen_name,
                "user_name": r.user.name,
                "text": text,
                "profile_image_url": getattr(r.user, "profile_image_url_https", None)
                                     or getattr(r.user, "profile_image_url", None),
                "created_at": r.created_at,
                "is_mine": str(r.user.id) == self.twitter_client.user_id,
            })

        return out

    # ────────────────────────────────────────────────────────────────────────────
    async def send_reply(self, tweet_id: int, tweet_text: str) -> dict:
        """
        주어진 tweet_id에 리플(댓글)을 전송하고, DB 로그 남긴 뒤 결과 반환
        """
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        try:
            tweet = await client.get_tweet_by_id(str(tweet_id))
        except TwikitNotFound:
            raise NotFoundError(f"Tweet {tweet_id} not found")
        except Exception as e:
            logger.error(f"Tweet 검색 실패 (send_reply): {e}")
            raise

        if not tweet:
            raise NotFoundError(f"Tweet {tweet_id} not found")

        # 1) Twikit으로 답글 생성
        try:
            result = await client.create_tweet(text=tweet_text, reply_to=str(tweet_id))
        except Exception as e:
            logger.error(f"답글 생성 실패: {e}")
            raise

        # 2) DB에 로그 남기기
        log = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
        self.repo.add_reply_log(log)
        try:
            await self.repo.commit()
        except Exception as e:
            logger.error(f"답글 로그 저장 실패: {e}")
            await self.repo.rollback()

        # 3) Twikit Tweet 객체 → dict 변환
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

    # ────────────────────────────────────────────────────────────────────────────
    async def delete_reply(self, reply_id: int) -> None:
        """
        주어진 reply_id(트윗 ID)에 해당하는 리플라이를 삭제하고 DB 로그에서도 삭제
        """
        await self.twitter_client.ensure_login()
        client = self.twitter_client.get_client()

        try:
            await client.delete_tweet(str(reply_id))
        except TwikitNotFound:
            raise NotFoundError(f"Reply {reply_id} not found")
        except Exception as e:
            logger.error(f"리플라이 삭제 실패: {e}")
            raise

        # DB에서 로그 삭제
        await self.repo.delete_reply_log(reply_id)

    # ────────────────────────────────────────────────────────────────────────────
    async def sync_latest_tweets(
        self,
        screen_name: str,
        remote_cursor: Optional[str] = None,
        batch_size: int = 20
    ) -> str:
        """
        기존에 호출되던 sync_latest_tweets
        내부적으로 synchronize_tweets를 호출
        """
        return await self.synchronize_tweets(screen_name, remote_cursor, batch_size)