"""
LLM 서비스 관련 예외 클래스들
"""

from app.utils.exceptions import ApiError


class LLMServiceError(ApiError):
    """LLM 서비스 관련 기본 예외"""
    pass


class LLMChainError(LLMServiceError):
    """LLM 체인 관련 오류"""
    pass


class TranslationError(LLMChainError):
    """번역 관련 오류"""
    pass


class ClassificationError(LLMChainError):
    """분류 관련 오류"""
    pass


class ScheduleExtractionError(LLMChainError):
    """스케줄 추출 관련 오류"""
    pass


class ReplyGenerationError(LLMChainError):
    """답글 생성 관련 오류"""
    pass


class PromptBuildError(LLMServiceError):
    """프롬프트 생성 관련 오류"""
    pass


class LLMConfigurationError(LLMServiceError):
    """LLM 설정 관련 오류"""
    pass


class RAGServiceError(LLMServiceError):
    """RAG 서비스 관련 오류"""
    pass