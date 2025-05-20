# app/services/llm/pipeline_service.py
import asyncio
from typing import Optional

from app.services.llm.chains import TranslationChain, ClassificationChain, ScheduleChain, ReplyChain
from app.services.llm.masking_utils import (
    mask_rt_prefix, restore_rt_prefix,
    mask_hash_emoji, restore_hash_emoji, extract_emojis
)
from app.schemas.llm_schema import TranslationResult, ReplyResult

class LLMPipelineService:
    def __init__(self, rag_service):
        self.trans_chain = TranslationChain(rag_service)
        self.class_chain = ClassificationChain(rag_service)
        self.sched_chain = ScheduleChain()
        self.reply_chain = ReplyChain()

    async def translate(self, text: str, timestamp: str) -> TranslationResult:
        # 1) RT·#⃣ 마스킹 & 이모지 보존
        masked, hash_em = mask_hash_emoji(text)
        masked, rt_pref = mask_rt_prefix(masked)
        orig_emojis = extract_emojis(text)

        # 2) **번역만** 수행
        translated_masked = await asyncio.to_thread(self.trans_chain.run, masked, timestamp)

        # 3) 마스킹 복원
        trans = restore_rt_prefix(translated_masked, rt_pref)
        trans = restore_hash_emoji(trans, hash_em)

        # 4) 누락된 이모지는 맨 뒤에 추가
        missing = [e for e in orig_emojis if e not in trans]
        if missing:
            trans += "".join(missing)

        # 아직 분류/스케줄은 실행하지 않으므로 placeholder
        return TranslationResult(translated=trans, category="일반", start=None, end=None)

    async def classify(self, text: str) -> tuple[str, Optional[str], Optional[str]]:
        # 필요할 때만 분류
        raw = await asyncio.to_thread(self.class_chain.run, text)
        # raw 은 "카테고리 ␞ 제목 ␞ 상세정보" 또는 "일반 ␞ None ␞ None"
        final = raw.strip().split("␞")
        if (len(final) != 3):
            # fallback: 모두 None
            return "일반", None, None
        var = [s.strip() for s in final]
        return var[0], (None if var[1].lower() == "none" else var[1]), (None if var[2].lower() == "none" else var[2])


    async def extract_schedule(self, text: str, timestamp: str) -> tuple[str, str]:
        # 필요할 때만 일정 추출
        raw = await asyncio.to_thread(self.sched_chain.run, text, timestamp)
        start, end = [s.strip() for s in raw.split("␞", 1)]
        return (
            None if start.lower() == "none" else start,
            None if end.lower() == "none" else end,
        )

    async def generate_reply(self, text: str, contexts: list[str]) -> ReplyResult:
        # 리스트를 한 덩어리 문자열로 합치기
        contexts_str = "\n".join(f"- {c}" for c in contexts)
        def _sync_run():
            return self.reply_chain.run(text, contexts_str)
        reply_text = await asyncio.to_thread(_sync_run)
        return ReplyResult(reply_text=reply_text)