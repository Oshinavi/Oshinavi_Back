import asyncio
from typing import Optional

from app.services.llm.chains import (
    TranslationChain,
    ClassificationChain,
    ScheduleChain,
    ReplyChain,
)
from app.services.llm.masking_utils import (
    mask_rt_prefix,
    restore_rt_prefix,
    mask_hash_emoji,
    restore_hash_emoji,
    extract_emojis,
)
from app.schemas.llm_schema import TranslationResult, ReplyResult

class LLMPipelineService:
    def __init__(self, rag_service):
        self.trans_chain = TranslationChain(rag_service)
        self.class_chain = ClassificationChain(rag_service)
        self.sched_chain = ScheduleChain()
        self.reply_chain = ReplyChain()

    async def translate(self, text: str, timestamp: str) -> TranslationResult:
        # 1) RT/해시태그 마스킹 & 이모지 보존
        masked, hash_serialized = mask_hash_emoji(text)
        masked, rt_prefix       = mask_rt_prefix(masked)
        orig_emojis             = extract_emojis(text)

        # 2) 번역 체인 실행 (RAG + LLM)
        translated_masked = await asyncio.to_thread(
            self.trans_chain.run, masked, timestamp
        )

        # 3) 마스킹 토큰 복원
        trans = restore_rt_prefix(translated_masked, rt_prefix)
        trans = restore_hash_emoji(trans, hash_serialized)

        # 4) 누락된 이모지 뒤에 추가
        missing = [e for e in orig_emojis if e not in trans]
        if missing:
            trans += "".join(missing)

        # 아직 분류/스케줄은 실행하지 않으므로 placeholder 리턴
        return TranslationResult(
            translated=trans,
            category="일반",
            start=None,
            end=None,
        )

    async def classify(self, text: str) -> tuple[str, Optional[str], Optional[str]]:
        raw = await asyncio.to_thread(self.class_chain.run, text)
        # raw: "카테고리 ␞ 제목 ␞ 상세정보"
        parts = raw.strip().split("␞")
        if len(parts) != 3:
            return "일반", None, None
        cat, title, desc = (p.strip() for p in parts)
        return (
            cat,
            None if title.lower() == "none" else title,
            None if desc.lower()  == "none" else desc,
        )

    async def extract_schedule(self, text: str, timestamp: str) -> tuple[str, str]:
        raw = await asyncio.to_thread(self.sched_chain.run, text, timestamp)
        start, end = [s.strip() for s in raw.split("␞", 1)]
        return (
            None if start.lower() == "none" else start,
            None if end.lower()   == "none" else end,
        )

    async def generate_reply(self, text: str, contexts: list[str]) -> ReplyResult:
        contexts_str = "\n".join(f"- {c}" for c in contexts)
        def _sync_run():
            return self.reply_chain.run(text, contexts_str)
        reply_text = await asyncio.to_thread(_sync_run)
        return ReplyResult(reply_text=reply_text)