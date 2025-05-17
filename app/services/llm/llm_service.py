import logging
import re
from typing import Tuple, Dict

from openai import AsyncOpenAI
from app.services.llm.rag_service import RAGService
from app.services.llm.prompts import PromptType, SYSTEM_PROMPTS
from app.schemas.llm_schema import TranslationResult, ReplyResult

logger = logging.getLogger(__name__)

class LLMService:
    """
    LLM 기반 텍스트 처리 서비스
    - 트윗 텍스트 번역(Translation) 및 자동 리플라이(Reply) 기능 제공
    - RT 프리픽스 및 특정 이모지 마스킹/복원, RAG 컨텍스트 적용, OpenAI 호출, 결과 파싱 로직 포함
    """
    _RT_PATTERN    = re.compile(r"^RT @\S+:" )   # 리트윗 프리픽스 인식
    _HASH_EMOJI    = '#\u20E3'                   # 마스킹할 특수 이모지 (#⃣)
    _EMOJI_PATTERN = re.compile(
        r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]"
    )  # 이모지 보존 패턴

    def __init__(
            self,
            openai_client: AsyncOpenAI,
            rag_service: RAGService
    ):
        """
        Args:
          openai_client: OpenAI 비동기 클라이언트 인스턴스
          rag_service:   FAISS 기반 RAGService 인스턴스
        """
        self.openai = openai_client
        self.rag    = rag_service

    # ─── RT 프리픽스 마스킹 및 복원 ─────────────────────────────────

    def _extract_rt_prefix(self, text: str) -> str | None:
        m = self._RT_PATTERN.match(text)
        return m.group(0) if m else None

    def _mask_rt_prefix(self, text: str) -> Tuple[str, str | None]:
        prefix = self._extract_rt_prefix(text)
        if prefix:
            return text.replace(prefix, "__RT_PREFIX__ ", 1), prefix
        return text, None

    def _restore_rt_prefix(self, text: str, prefix: str | None) -> str:
        if not prefix:
            return text
        cleaned = text.replace("__RT_PREFIX__ ", "")
        return f"{prefix}{cleaned}"

    # ─── 특정 이모지 마스킹 및 복원 ─────────────────────────────────

    def _mask_hash_emoji(self, text: str) -> Tuple[str, str | None]:
        if self._HASH_EMOJI in text:
            return text.replace(self._HASH_EMOJI, "__HASH_EMOJI__"), self._HASH_EMOJI
        return text, None

    def _restore_hash_emoji(self, text: str, emoji: str | None) -> str:
        return text.replace("__HASH_EMOJI__", emoji) if emoji else text

    # ─── 트윗 번역 처리 ─────────────────────────────────────────

    async def translate(
            self,
            tweet_text: str,
            tweet_timestamp: str
    ) -> TranslationResult:
        """
        트윗 텍스트를 번역하고 LLM 분류 결과를 포함하여 반환

        과정:
          1) 특수 이모지(#⃣) 마스킹
          2) RT 프리픽스 마스킹
          3) 원본 이모지 추출
          4) RAG 컨텍스트 로드
          5) 시스템 프롬프트 구성
          6) OpenAI 호출
          7) 결과 파싱(␞ 구분자)
          8) RT, 특수 이모지 복원
          9) 이모지 후처리
        """
        # 1) 특수 이모지 마스킹
        masked, hash_emoji = self._mask_hash_emoji(tweet_text)
        # 2) RT 프리픽스 마스킹
        masked, rt_prefix = self._mask_rt_prefix(masked)
        # 3) 원본 이모지 추출
        orig_emojis = self._EMOJI_PATTERN.findall(tweet_text)

        # 4) RAG 컨텍스트 로드
        contexts = self.rag.get_context(masked)
        logger.info("[LLMService] 최종 RAG 컨텍스트: %s", contexts)

        # 5) 시스템 프롬프트 준비
        system = SYSTEM_PROMPTS[PromptType.TRANSLATE].format(timestamp=tweet_timestamp)
        enriched = (
            system
            + "\n\n### Reference dictionary:\n"
            + "\n".join(f"- {c}" for c in contexts)
            + "\n\n"
        )

        # 6) OpenAI 호출
        try:
            resp = await self.openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": enriched},
                    {"role": "user", "content": masked.strip()},
                ],
                temperature=0.3,
            )
            raw = resp.choices[0].message.content.strip()
            logger.info("[LLMService] Raw response: %s", raw)
            if raw.startswith("번역문"):
                raw = raw[len("번역문"):].lstrip()
            parts = [p.strip() for p in raw.split("␞", 3)]
            if len(parts) != 4:
                logger.warning("LLM 포맷 불일치: %s", parts)
                trans_masked = masked
                category = "일반"
                start_str = end_str = None
            else:
                trans_masked, category, start_str, end_str = parts
                start_str = None if start_str.lower() == "none" else start_str
                end_str = None if end_str.lower() == "none" else end_str
        except Exception as e:
            logger.error("[LLMService] 번역 오류, 기본값 사용: %s", e, exc_info=True)
            trans_masked = masked; category = "일반"; start_str = end_str = None

        # 8) 복원
        text = trans_masked
        text = self._restore_rt_prefix(text, rt_prefix)
        text = self._restore_hash_emoji(text, hash_emoji)

        # 9) 이모지 후처리: 원본 이모지 중 없어진 것은 끝에 추가
        missing = [em for em in orig_emojis if em not in text]
        if missing:
            text += "".join(missing)

        return TranslationResult(
            translated=text,
            category=category,
            start=start_str,
            end=end_str,
        )

    # ─── 자동 리플라이 생성 ────────────────────────────────────────
    async def reply(self, tweet_text: str) -> ReplyResult:
        """
        주어진 트윗 텍스트에 대해 LLM을 사용해 자동 리플라이 문장을 생성
        """
        system_prompt = SYSTEM_PROMPTS[PromptType.REPLY]
        try:
            resp = await self.openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": tweet_text.strip()},
                ],
                temperature=0.5,
            )
            return ReplyResult(reply_text=resp.choices[0].message.content.strip())
        except Exception as error:
            logger.error("[LLMService] 자동 리플라이 생성 오류: %s", error, exc_info=True)
            raise