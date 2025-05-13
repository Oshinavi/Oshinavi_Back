# app/services/llm/llm_service.py

import logging
import re
from openai import AsyncOpenAI
from app.services.llm.rag_service import RAGService
from app.services.llm.prompts import PromptType, SYSTEM_PROMPTS
from app.schemas.llm_schema import TranslationResult, ReplyResult
from typing import Tuple

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, openai_client: AsyncOpenAI, rag: RAGService):
        self.openai = openai_client
        self.rag    = rag

    # ─── 해시태그 마스킹 헬퍼 ─────────────────────────────────
    _HT_PATTERN = re.compile(r'#\S+')

    def _extract_hashtags(self, text: str) -> list[str]:
        # 순서대로 중복 제거
        tags = self._HT_PATTERN.findall(text)
        seen = set()
        out = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def _mask_hashtags(self, text: str) -> Tuple[str, dict[str,str]]:
        tags = self._extract_hashtags(text)
        mapping: dict[str,str] = {}
        masked = text
        for i, tag in enumerate(tags, start=1):
            placeholder = f"__HT_{i}__"
            mapping[placeholder] = tag
            # 정규식이 아닌 replaceAll 로 치환
            masked = masked.replace(tag, placeholder)
        return masked, mapping

    def _restore_placeholders(self, text: str, mapping: dict[str,str]) -> str:
        out = text
        for placeholder, tag in mapping.items():
            out = out.replace(placeholder, tag)
        return out

    def _force_restore_hashtags(self, original: str, translated: str) -> str:
        orig_tags = self._extract_hashtags(original)
        idx = 0
        def repl(m):
            nonlocal idx
            if idx < len(orig_tags):
                t = orig_tags[idx]
                idx += 1
                return t
            return m.group(0)
        return self._HT_PATTERN.sub(repl, translated)

    # ─── 번역 본문 ──────────────────────────────────────────
    async def translate(self, tweet_text: str, tweet_timestamp: str) -> TranslationResult:
        # 0) 해시태그 마스킹
        masked_text, ht_mapping = self._mask_hashtags(tweet_text)

        # 1) RAG 컨텍스트
        contexts = self.rag.get_context(masked_text)
        logger.info(f"[LLMService] ▶ RAG contexts: {contexts}")

        # 2) 시스템 프롬프트 조합
        system = SYSTEM_PROMPTS[PromptType.TRANSLATE].format(timestamp=tweet_timestamp)
        enriched = system + "\n\n### Reference dictionary:\n" \
                   + "\n".join(f"- {c}" for c in contexts) + "\n\n"

        # 3) OpenAI 호출
        try:
            resp = await self.openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": enriched},
                    {"role": "user",   "content": masked_text.strip()},
                ],
                temperature=0.3
            )
            content = resp.choices[0].message.content.strip()
            logger.info(f"[LLMService] ▶ Raw LLM response:\n{content}")

            # 4) 결과 파싱 (␞ 구분)
            if content.startswith("번역문"):
                content = content[len("번역문"):].lstrip()
            parts = [p.strip() for p in content.split("␞", 3)]
            if len(parts) != 4:
                logger.warning(f"LLM 포맷 불일치(␞ split): {parts!r}, 원문: {content!r}")
                translated_masked = masked_text
                category = "일반"
                start_str = end_str = None
            else:
                translated_masked, category, start_str, end_str = parts
                start_str = None if start_str.lower() == "none" else start_str
                end_str   = None if end_str.lower()   == "none" else end_str

        except Exception as e:
            logger.error("[LLMService] LLM translate error, 기본값으로 대체합니다", exc_info=True)
            translated_masked = masked_text
            category = "일반"
            start_str = end_str = None

        # 5) 플레이스홀더 역치환
        translated = self._restore_placeholders(translated_masked, ht_mapping)

        # 6) 정규식 보강 (혹시 LLM이 해시태그를 만졌다면)
        translated = self._force_restore_hashtags(tweet_text, translated)

        return TranslationResult(
            translated=translated,
            category=category,
            start=start_str,
            end=end_str
        )

    async def reply(self, tweet_text: str) -> ReplyResult:
        system = SYSTEM_PROMPTS[PromptType.REPLY]
        try:
            resp = await self.openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": tweet_text.strip()},
                ],
                temperature=0.5
            )
            return ReplyResult(reply_text=resp.choices[0].message.content.strip())
        except Exception as e:
            logger.error("[LLMService] LLM reply error", exc_info=e)
            raise