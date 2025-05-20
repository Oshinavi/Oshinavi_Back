# import logging
# import re
# from typing import List
#
# from openai import AsyncOpenAI
# from app.services.llm.prompt_templates import PromptType, SYSTEM_PROMPTS
# from app.services.llm.rag_service import RAGService
# from app.schemas.llm_schema import TranslationResult
#
# logger = logging.getLogger(__name__)
#
# class TranslateService:
#     """
#     트윗 번역 및 정보 추출 서비스 클래스
#     - RAGService로부터 용어 사전을 참조하여 번역 정확도 상승
#     - 시스템 및 사용자 메시지 구성, OpenAI 호출, 결과 파싱 로직 포함
#     """
#     def __init__(
#         self,
#         openai_client: AsyncOpenAI,
#         rag_service: RAGService,
#         model_name: str = "gpt-4.1-mini-2025-04-14"
#     ):
#         """
#         Args:
#           openai_client: OpenAI 비동기 클라이언트 인스턴스
#           rag_service:   용어 사전 제공을 위한 RAGService 인스턴스
#           model_name:    사용할 OpenAI 모델 이름
#         """
#         self.openai = openai_client
#         self.rag    = rag_service
#         self.model  = model_name
#
#     async def translate(
#             self,
#             tweet_text: str,
#             tweet_timestamp: str
#     ) -> TranslationResult:
#         """
#         트윗 텍스트를 한국어로 번역하고 분류 및 일정 정보를 추출
#
#         Steps:
#           1) RAGService를 통해 용어 사전 컨텍스트 획득
#           2) 시스템 프롬프트 및 참조 용어 블록 구성
#           3) OpenAI ChatCompletion API 호출
#           4) 응답 결과를 슬래시('/') 구분자로 파싱
#           5) TranslationResult 모델로 결과 반환
#
#         Args:
#           tweet_text:      원본 트윗 텍스트
#           tweet_timestamp: 트윗 작성 시각("YYYY-MM-DD HH:MM:SS")
#         """
#
#         # 1) RAG로부터 고유명사 컨텍스트 가져오기
#         context_items = self.rag.get_context(tweet_text)
#         logger.info("[TranslateService] 최종 RAG 컨텍스트: %s", context_items)
#         reference_block = "\n".join(f"- {item}" for item in context_items)
#
#         # 2) 시스템 프롬프트 구성
#         system_prompt = SYSTEM_PROMPTS[PromptType.TRANSLATE].format(
#             timestamp=tweet_timestamp
#         )
#         enriched_prompt = (
#                 system_prompt
#                 + "\n\n### Reference dictionary:\n"
#                 + reference_block
#                 + "\n\n"
#         )
#
#         try:
#             # 3) OpenAI Chat API 호출
#             response = await self.openai.chat.completions.create(
#                 model=self.model,
#                 messages=[
#                     {"role": "system", "content": enriched_prompt},
#                     {"role": "user", "content": tweet_text.strip()},
#                 ],
#                 temperature=0.3
#             )
#             raw_output = response.choices[0].message.content.strip()
#             logger.info("[TranslateService] Raw response: %s", raw_output)
#
#             # 4) 슬래시 구분자 기반 파싱 (ignoring brackets)
#             parts = [p.strip() for p in self._split_ignore_brackets(raw_output)]
#             if len(parts) != 4:
#                 raise ValueError(
#                     f"응답 형식 오류: 4개 요소 필요, 현재 {len(parts)}개"  # noqa
#                 )
#             translated_text, category, start_str, end_str = parts
#             start_val = None if start_str.lower() == "none" else start_str
#             end_val = None if end_str.lower() == "none" else end_str
#
#             logger.debug(
#                 "[TranslateService] Parsed: translated=%s, category=%s, start=%s, end=%s",
#                 translated_text, category, start_val, end_val
#             )
#
#             # 5) TranslationResult 반환
#             return TranslationResult(
#                 translated=translated_text,
#                 category=category,
#                 start=start_val,
#                 end=end_val
#             )
#
#         except Exception as error:
#             logger.error("[TranslateService] 번역 처리 중 오류: %s", error, exc_info=True)
#             raise
#
#     def _split_ignore_brackets(self, text: str) -> List[str]:
#         """
#         슬래시('/')를 기준으로 분할하되,
#         '「...」' 블록 내의 슬래시는 무시하도록 처리
#
#         Steps:
#           1) 따옴표 블록 내부 슬래시를 임시 마스킹
#           2) 마스킹된 텍스트를 '/'로 분할
#           3) 마스킹된 문자를 다시 복원
#         """
#         # 1) 블록 내부 슬래시 마스킹
#         def mask_slash(match: re.Match) -> str:
#             return match.group(0).replace('/', '\ue000')
#
#         masked_text = re.sub(r'「[^」]*」', mask_slash, text)
#         # 2) 외부 슬래시로 분할
#         raw_parts = masked_text.split('/')
#         # 3) 마스킹 복원
#         return [part.replace('\ue000', '/') for part in raw_parts]