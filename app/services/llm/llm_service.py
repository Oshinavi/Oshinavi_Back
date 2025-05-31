import logging
from typing import Optional, Tuple, List

from app.services.llm.pipeline_service import LLMPipelineService
from app.schemas.llm_schema import TranslationResult, ReplyResult

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM 기반 파이프라인 서비스
    - 번역, 분류, 일정 추출, 리플라이 생성을 담당하는 파이프라인 래퍼

    Args:
        pipeline: LLMPipelineService 인스턴스
    """
    def __init__(self, pipeline: LLMPipelineService):
        self.pipeline = pipeline

    async def translate(self, text: str, timestamp: str) -> TranslationResult:
        """
        텍스트 번역 수행

        Args:
            text: 번역할 원문 텍스트
            timestamp: 참조할 시간 정보
        Returns:
            TranslationResult: 번역 결과 객체
        """
        return await self.pipeline.translate(text, timestamp)

    async def classify(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        텍스트 분류 및 일정 여부 추출

        Args:
            text: 분류할 텍스트
        Returns:
            Tuple[category, start_time, end_time]
        """
        return await self.pipeline.classify(text)

    async def extract_schedule(self, text: str, timestamp: str) -> Tuple[Optional[str], Optional[str]]:
        """
        텍스트로부터 일정 정보 추출

        Args:
            text: 일정 정보를 포함할 원문
            timestamp: 기준 시간 정보
        Returns:
            Tuple[start_time, end_time]
        """
        return await self.pipeline.extract_schedule(text, timestamp)

    async def reply(self, text: str, contexts: List[str]) -> ReplyResult:
        """
        자동 리플라이 생성

        Args:
            text: 원문 텍스트
            contexts: 참조할 기존 리플라이 목록 (리스트 형태)
        Returns:
            ReplyResult: 생성된 리플라이 결과 객체
        """
        return await self.pipeline.generate_reply(text, contexts)