"""
LLM 스키마 정의 모듈
- LLM 번역 및 자동 응답 결과를 위한 Pydantic 모델을 포함
"""

from pydantic import BaseModel
from typing  import Optional

class TranslationResult(BaseModel):
    """
    LLM 번역 및 분류 결과를 나타내는 모델

    속성:
      translated: LLM이 번역한 텍스트
      category:   LLM이 분류한 카테고리 (예: '일반', '경고' 등)
      start:      LLM이 추출한 이벤트 시작 시각 문자열 (선택적)
      end:        LLM이 추출한 이벤트 종료 시각 문자열 (선택적)
    """
    translated: str            # 번역된 텍스트
    category:   str            # 분류 카테고리
    start:      Optional[str] = None  # 이벤트 시작 시각 (YYYY.MM.DD HH:MM:SS)
    end:        Optional[str] = None  # 이벤트 종료 시각 (YYYY.MM.DD HH:MM:SS)

class ReplyResult(BaseModel):
    """
    LLM을 이용해 생성된 자동 리플라이 결과를 나타내는 모델

    속성:
      reply_text: 생성된 리플라이 텍스트
    """
    reply_text: str  # 자동 생성된 리플라이 텍스트