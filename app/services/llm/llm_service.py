# app/services/llm/llm_service.py
import logging
from typing import Optional

from app.services.llm.pipeline_service import LLMPipelineService
from app.schemas.llm_schema import TranslationResult, ReplyResult

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, pipeline: LLMPipelineService):
        """
        Args:
        pipeline: 번역·분류·일정·리플라이 체인을 묶은 파이프라인 서비스
        """
        self.pipeline = pipeline

    async def translate(self, text: str, timestamp: str) -> TranslationResult:
        return await self.pipeline.translate(text, timestamp)

    async def classify(self, text: str) -> tuple[str, Optional[str], Optional[str]]:
        return await self.pipeline.classify(text)

    async def extract_schedule(self, text: str, timestamp: str) -> tuple[str, str]:
        return await self.pipeline.extract_schedule(text, timestamp)

    async def reply(self, text: str) -> ReplyResult:
        return await self.pipeline.generate_reply(text)