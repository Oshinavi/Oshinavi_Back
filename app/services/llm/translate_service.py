# app/services/llm/translate_service.py

import logging
import re
from typing import List
from openai import AsyncOpenAI
from app.services.llm.prompts import PromptType, SYSTEM_PROMPTS
from app.services.llm.rag_service import RAGService
from app.schemas.llm_schema import TranslationResult

logger = logging.getLogger(__name__)

class TranslateService:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        rag: RAGService,
        model: str = "gpt-4o-mini-2024-07-18"
    ):
        self.openai = openai_client
        self.rag    = rag
        self.model  = model

    async def translate(self, tweet_text: str, tweet_timestamp: str) -> TranslationResult:
        # 1) RAG 로부터 고유명사 컨텍스트 가져오기
        contexts = self.rag.get_context(tweet_text)
        context_block = "\n".join(f"- {c}" for c in contexts)

        # 2) 시스템 프롬프트 준비
        system = SYSTEM_PROMPTS[PromptType.TRANSLATE].format(timestamp=tweet_timestamp)
        enriched = (
            system
            + "\n\n### Reference dictionary:\n"
            + context_block
            + "\n\n"
        )

        try:
            # 3) OpenAI Chat API 호출
            resp = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": enriched},
                    {"role": "user",   "content": tweet_text.strip()},
                ],
                temperature=0.3
            )
            content = resp.choices[0].message.content.strip()
            logger.info("[TranslateService] ▶ Raw LLM response:\n%s", content)

            # 4) 「」 안의 '/'만 특수문자로 마스킹 → 외부 '/' 로 분할 → 마스킹 복원
            parts = [p.strip() for p in self._split_ignore_brackets(content)]
            if len(parts) != 4:
                raise ValueError(
                    f"응답 형식 오류: '번역문 / 분류 / 시작 일자 / 종료 일자' 네 개로 구분되어야 합니다. (got {len(parts)} parts)"
                )

            translated, category, start_str, end_str = parts
            start = None if start_str.lower() == "none" else start_str
            end   = None if end_str.lower()   == "none" else end_str

            logger.info(
                "[TranslateService] ▶ Parsed fields:\n"
                "   번역문 : %s\n"
                "   분류   : %s\n"
                "   시작일자: %s\n"
                "   종료일자: %s",
                translated, category, start, end
            )

            return TranslationResult(
                translated=translated,
                category=category,
                start=start,
                end=end,
            )

        except Exception as e:
            logger.error("LLM translate error: %s", e, exc_info=True)
            raise

    def _split_ignore_brackets(self, text: str) -> List[str]:
        """
        1) 「…」 블록 안의 '/' 를 U+E000 영역으로 마스킹
        2) 남은 '/' 로만 text.split('/')
        3) 마스킹된 문자를 원래 '/' 로 복원
        """
        # 1) mask slashes inside 「…」
        def _mask(m: re.Match) -> str:
            return m.group(0).replace('/', '\ue000')

        masked = re.sub(r'「[^」]*」', _mask, text)
        # 2) 외부 슬래시로 분할
        raw_parts = masked.split('/')
        # 3) 마스킹을 다시 슬래시로
        return [part.replace('\ue000', '/') for part in raw_parts]



# import re
# import logging
# from typing import Optional, Dict
# from app.utils.ollama_client import OllamaClient
# from app.services.ai.rag_service import RAGService
# from app.core.config import settings
#
# logger = logging.getLogger(__name__)
#
# ollama = OllamaClient(settings.ollama_api_url, settings.ollama_model)
#
# rag = RAGService(
#     index_path="vector_store/faiss_index.bin",
#     meta_path="vector_store/metadata.json",
#     embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
#     top_k=3
# )
#
# SYSTEM_PROMPT = """
# You are an AI that processes Japanese tweets along with their timestamps.
# Tweet was posted on: {timestamp}
#
# Your tasks are:
# - Translate the tweet into Korean while keeping hashtags in their original Japanese form.
# - Identify whether the tweet is about one of the following categories: 일반, 방송, 라디오, 라이브, 음반, 굿즈, 영상, 게임.
# - ONLY IF the tweet explicitly includes a date or time:
#     • an absolute date/time (e.g. '5/5(月) 20:30') or
#     • a relative date immediately followed by a time (e.g. '今日20時') or
#     • a “～まで” expression indicating an end bound (e.g. '今日まで', '明日まで')
#     • a “～から” expression indicating a start bound (e.g. '明日15時から', '5/5 10:00から')
#     • Extract it in the format 'YYYY.MM.DD HH:MM:SS'.
#     • To resolve relative dates like:
#         – '明日' alone, only if paired with a time (e.g. '明日15時').
#         – '~まで': treat as an **end date/time** at that day’s 23:59:59.
#         – '～から': treat as a **start date/time** at the specified moment.
#     • If only a start date/time is present, set the end date/time to exactly one hour after the start.
#     • If only an end date/time is present, set the start date/time to that day at 00:00:00.
#     • If both start and end date/times are present, use them as given.
#   If no date/time information is present, output None for both.
# - If the tweet is not about 일반 or 굿즈, specify the related program, event, or media in Korean.
# - Do not add emojis that are not in the original text.
#
# Format your response exactly as:
#   번역문 / 분류 / 시작 일자 / 종료 일자
# """
#
#
# async def translate_japanese_tweet(tweet_text: str, tweet_timestamp: str) -> Dict[str, Optional[str]]:
#     """
#     일본어 트윗을 한국어로 번역하고, 카테고리 및 일정 정보 추출
#
#     :param tweet_text: 트윗 원문
#     :param tweet_timestamp: 트윗의 원본 타임스탬프
#     :return: 번역, 분류, 시작일, 종료일을 담은 딕셔너리
#     """
#     # RAG를 통해 고유명사 사전에서 관련 컨텍스트 추출
#     contexts = rag.get_context(tweet_text)
#     context_block = "\n".join(f"- {c}" for c in contexts)
#     enriched_system = SYSTEM_PROMPT.format(timestamp=tweet_timestamp) + "\n\n" + \
#         "### Reference dictionary:\n" + context_block + "\n\n"
#
#     # 메시지 조합
#     messages = [
#         {"role": "system", "content": enriched_system},
#         {"role": "user", "content": tweet_text.strip()}
#     ]
#
#     try:
#         result = await ollama.chat(messages, temperature=0.3)
#         logger.info(f"🔍 Ollama 응답: {result}")
#
#         # 응답 포맷 확인 및 분리
#         parts = [p.strip() for p in re.split(r"\s*/\s*", result)]
#         if len(parts) != 4:
#             raise ValueError("응답 형식 오류: '번역문 / 분류 / 시작 일자 / 종료 일자'")
#
#         translated, category, start_raw, end_raw = parts
#         return {
#             "translated": translated,
#             "category": category,
#             "start": None if start_raw.lower() == "none" else start_raw,
#             "end": None if end_raw.lower() == "none" else end_raw
#         }
#
#
#     except Exception as e:
#         logger.error(f"❗ 변환 오류: {e}")
#         return {
#             "translated": None,
#             "category": None,
#             "start": None,
#             "end": None,
#             "error": str(e)
#         }