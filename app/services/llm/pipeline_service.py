import asyncio
from typing import Optional, Tuple, List

from app.services.llm.chains import (
    TranslationChain,
    ClassificationChain,
    ScheduleChain,
    ReplyChain,
)
from app.services.llm.text_utils import TextMasker
from app.schemas.llm_schema import TranslationResult, ReplyResult

mask_rt_prefix = TextMasker.mask_rt_prefix
restore_rt_prefix = TextMasker.restore_rt_prefix
mask_hashtags = TextMasker.mask_hashtags
restore_hashtags = TextMasker.restore_hashtags
extract_emojis = TextMasker.extract_emojis


class LLMPipelineService:
    """
    LLM 기반 파이프라인 서비스
    - 번역, 분류, 일정 추출, 리플라이 생성 전체 흐름 관리
    """
    def __init__(self, rag_service):
        self.trans_chain = TranslationChain(rag_service)
        self.class_chain = ClassificationChain(rag_service)
        self.sched_chain = ScheduleChain()
        self.reply_chain = ReplyChain()

    async def translate(self, text: str, timestamp: str) -> TranslationResult:
        """
        번역 파이프라인:
        1) 해시태그, RT 접두사 마스킹 및 이모지 보존
        2) LLM 번역 실행
        3) 마스킹 복원 및 누락 이모지 추가
        """
        # 1) 전처리
        masked, tags = mask_hashtags(text)
        masked, rt_prefix = mask_rt_prefix(masked)
        emojis = extract_emojis(text)

        # 2) 번역 실행 (동기 체인을 각각 개별 스레드로)
        translated_masked = await asyncio.to_thread(
            self.trans_chain.run, masked, timestamp
        )

        # 3) 후처리
        restored = restore_rt_prefix(translated_masked, rt_prefix)
        restored = restore_hashtags(restored, tags)
        missing = [e for e in emojis if e not in restored]
        if missing:
            restored += "".join(missing)

        return TranslationResult(
            translated=restored,
            category="일반",
            start=None,
            end=None,
        )

    async def classify(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        분류 및 제목/상세정보 추출
        """
        raw = await asyncio.to_thread(self.class_chain.run, text)
        parts = [p.strip() for p in raw.split("␞")]  # 카테고리␞제목␞상세정보
        if len(parts) != 3:
            return "일반", None, None
        cat, title, desc = parts
        return (
            cat,
            None if title.lower() == "none" else title,
            None if desc.lower()  == "none" else desc,
        )

    async def extract_schedule(self, text: str, timestamp: str) -> Tuple[Optional[str], Optional[str]]:
        """
        일정(start, end) 정보 추출
        """
        raw = await asyncio.to_thread(self.sched_chain.run, text, timestamp)
        start, end = [s.strip() for s in raw.split("␞", 1)]
        return (
            None if start.lower() == "none" else start,
            None if end.lower()   == "none" else end,
        )

    async def generate_reply(self, text: str, contexts: List[str]) -> ReplyResult:
        """
        자동 리플라이 생성
        """
        # contexts는 리스트 타입으로 직접 전달
        reply_text = await asyncio.to_thread(
            self.reply_chain.run,
            text,
            contexts
        )
        return ReplyResult(reply_text=reply_text)