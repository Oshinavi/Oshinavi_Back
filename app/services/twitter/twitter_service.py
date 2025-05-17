# app/services/twitter/twitter_service.py

import json
import logging
from datetime import datetime, timedelta
from typing import Union, Optional, List, Tuple

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
            except:
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


# # app/services/twitter/twitter_service.py
#
# import json
# import logging
# from datetime import datetime, timedelta
# from typing import Union, Optional, List, Tuple
#
# from sqlalchemy.exc import IntegrityError
# from selenium.common.exceptions import TimeoutException
#
# from app.models.reply_log import ReplyLog
# from app.models.post import Post
# from app.repositories.tweet_repository import TweetRepository
# from app.services.twitter.twitter_client_service import TwitterClientService
# from app.services.twitter.twitter_user_service import TwitterUserService
# from app.services.llm.llm_service import LLMService
# from app.schemas.llm_schema import TranslationResult
# from app.utils.tco_resolver import TcoResolver
# from app.utils.exceptions import NotFoundError
#
# logger = logging.getLogger(__name__)
#
# class TwitterService:
#     """
#     최신 트윗 저장 및 리플라이 전송
#     """
#     def __init__(
#         self,
#         db,
#         llm_service: LLMService,
#         user_internal_id: str,
#     ):
#         self.repo           = TweetRepository(db)
#         self.llm            = llm_service
#         self.twitter_client = TwitterClientService(user_internal_id)
#         self.twitter_user   = TwitterUserService(self.twitter_client)
#         self.resolver       = TcoResolver()
#
#     async def _extract_image_urls(self, media_entries: list) -> List[str]:
#         """
#         twikit media 객체 대신 t.co 링크를 TcoResolver 로 처리
#         — 사진(photo) 타입만 가져오고, 영상이나 GIF는 건너뜁니다.
#         — Selenium 타임아웃 등 에러 발생 시 그냥 무시하고 넘어갑니다.
#         """
#         raw_urls = []
#         for m in media_entries or []:
#             if getattr(m, "type", None) != "photo":
#                 continue
#             url = getattr(m, "media_url_https", None) or getattr(m, "url", None)
#             if url:
#                 raw_urls.append(url)
#
#         resolved = []
#         for url in raw_urls:
#             try:
#                 imgs = await self.resolver.resolve([url])
#             except TimeoutException:
#                 logger.warning("이미지 추출 타임아웃, 건너뜀: %s", url)
#                 continue
#             except Exception as e:
#                 logger.error("미디어 URL 처리 오류 %s: %s", url, e, exc_info=True)
#                 continue
#
#             if imgs:
#                 resolved.extend(imgs)
#
#         return resolved
#
#     async def fetch_and_store_latest_tweets(
#         self,
#         screen_name: str,
#         count: int = 20,
#         cursor: Optional[str] = None
#     ) -> Tuple[List[dict], Optional[str]]:
#         # 1) 로그인
#         await self.twitter_client.ensure_login()
#
#         # 2) 사용자 정보 조회
#         user = await self.twitter_user.get_user_info(screen_name)
#         if not user:
#             raise NotFoundError(f"User '{screen_name}' not found")
#
#         author_id         = str(user["id"])
#         profile_image_url = user.get("profile_image_url")
#         client            = self.twitter_client.get_client()
#
#         # 3) 트윗 페치
#         tweets = await client.get_user_tweets(
#             user_id=author_id,
#             tweet_type="Tweets",
#             count=count,
#             cursor=cursor,
#         )
#         next_cursor = getattr(tweets, "next_cursor", None)
#
#         # --- DB에 이미 저장된 ID, 기존 포스트 조회 ---
#         existing_ids = set(await self.repo.list_tweet_ids())
#         all_posts    = await self.repo.list_posts_by_username(screen_name)
#         posts_map    = {p.tweet_id: p for p in all_posts}
#
#         serialized: List[dict] = []
#         new_posts: List[Post] = []
#
#         for t in tweets:
#             tid = int(t.id)
#
#             # DB에 이미 있으면, 저장된 값을 직렬화만
#             if tid in existing_ids:
#                 p = posts_map[tid]
#                 serialized.append({
#                     "tweet_userid": p.author.twitter_id,
#                     "tweet_id":     p.tweet_id,
#                     "tweet_username": p.author.username,
#                     "tweet_date":   p.tweet_date.strftime("%Y-%m-%d %H:%M:%S"),
#                     "tweet_text":   p.tweet_text,
#                     "tweet_translated_text": p.tweet_translated_text,
#                     "tweet_about":  p.tweet_about,
#                     "tweet_included_start_date": (
#                         p.tweet_included_start_date.strftime("%Y-%m-%d %H:%M:%S")
#                         if p.tweet_included_start_date else None
#                     ),
#                     "tweet_included_end_date": (
#                         p.tweet_included_end_date.strftime("%Y-%m-%d %H:%M:%S")
#                         if p.tweet_included_end_date else None
#                     ),
#                     "image_urls": json.loads(p.image_urls) if p.image_urls else [],
#                     "profile_image_url": profile_image_url,
#                 })
#                 continue
#
#             # 새로운 트윗: 번역 및 이미지 추출
#             text = t.full_text
#             date_str = _format_dt(t.created_at)
#             try:
#                 tr: TranslationResult = await self.llm.translate(text, date_str)
#             except Exception:
#                 tr = TranslationResult(
#                     translated=text,
#                     category="일반",
#                     start=None,
#                     end=None,
#                 )
#
#             img_urls = await self._extract_image_urls(t.media)
#             tweet_date = _parse_any_datetime(t.created_at)
#
#             # DB에 저장
#             post = Post(
#                 tweet_id                  = tid,
#                 author_internal_id        = author_id,
#                 tweet_date                = tweet_date,
#                 tweet_included_start_date = _parse_any_datetime(tr.start),
#                 tweet_included_end_date   = _parse_any_datetime(tr.end),
#                 tweet_text                = text,
#                 tweet_translated_text     = tr.translated,
#                 tweet_about               = tr.category,
#                 image_urls                = json.dumps(img_urls),
#             )
#             self.repo.add_post(post)
#             new_posts.append(post)
#
#             serialized.append({
#                 "tweet_userid": screen_name,
#                 "tweet_id":     tid,
#                 "tweet_username": screen_name,
#                 "tweet_date":   date_str,
#                 "tweet_text":   text,
#                 "tweet_translated_text": tr.translated,
#                 "tweet_about":  tr.category,
#                 "tweet_included_start_date": tr.start,
#                 "tweet_included_end_date": tr.end,
#                 "image_urls": img_urls,
#                 "profile_image_url": profile_image_url,
#             })
#
#         # 새로운 포스트가 있으면 커밋
#         if new_posts:
#             try:
#                 await self.repo.commit()
#             except IntegrityError:
#                 logger.warning("중복 엔트리 충돌, 롤백")
#                 await self.repo.rollback()
#
#         return serialized, next_cursor
#
#     async def send_reply(self, tweet_id: int, tweet_text: str) -> dict:
#         await self.twitter_client.ensure_login()
#         client = self.twitter_client.get_client()
#
#         tweet = await client.get_tweet_by_id(str(tweet_id))
#         if not tweet:
#             raise NotFoundError("해당 트윗이 존재하지 않습니다.")
#
#         result = await client.create_tweet(text=tweet_text, reply_to=str(tweet_id))
#         log    = ReplyLog(post_tweet_id=tweet_id, reply_text=tweet_text)
#         self.repo.add_reply_log(log)
#         await self.repo.commit()
#
#         return {
#             "reply_tweet_id": str(result.id),
#             "created_at":     result.created_at,
#             "text":           result.text,
#         }
#
# def _parse_any_datetime(dt: Union[str, datetime, None]) -> Optional[datetime]:
#     if not dt:
#         return None
#     if isinstance(dt, datetime):
#         return dt
#     s = dt.strip()
#     try:
#         utc = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
#         return utc + timedelta(hours=9)
#     except Exception:
#         pass
#     try:
#         return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
#     except Exception:
#         return None
#
#
# def _format_dt(dt: Union[str, datetime]) -> str:
#     if isinstance(dt, datetime):
#         return dt.strftime("%Y-%m-%d %H:%M:%S")
#     return dt  # 이미 문자열이면 그대로 반환