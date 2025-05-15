import logging
import re
from typing import Tuple, Dict

from openai import AsyncOpenAI
from app.services.llm.rag_service import RAGService
from app.services.llm.prompts import PromptType, SYSTEM_PROMPTS
from app.schemas.llm_schema import TranslationResult, ReplyResult

logger = logging.getLogger(__name__)

class LLMService:
    """
    LLM 기반 텍스트 처리 서비스
    - 트윗 텍스트 번역(Translation) 및 자동 리플라이(Reply) 기능 제공
    - 해시태그 마스킹, RAG 컨텍스트 적용, OpenAI 호출, 결과 파싱 로직 포함
    """
    _HT_PATTERN = re.compile(r"#\S+")  # 해시태그 인식 패턴

    def __init__(
            self,
            openai_client: AsyncOpenAI,
            rag_service: RAGService
    ):
        """
        Args:
          openai_client: OpenAI 비동기 클라이언트 인스턴스
          rag_service:   FAISS 기반 RAGService 인스턴스
        """
        self.openai = openai_client
        self.rag    = rag_service

    # ─── 해시태그 마스킹 및 복원 ─────────────────────────────────

    def _extract_hashtags(self, text: str) -> list[str]:
        """
        텍스트 내에서 해시태그(#...)를 추출하고 순서대로 중복 제거하여 반환
        """
        tags = self._HT_PATTERN.findall(text)
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        return unique_tags

    def _mask_hashtags(self, text: str) -> Tuple[str, dict[str,str]]:
        """
        해시태그를 임시 플레이스홀더로 치환하여 번역 시 보존
        Returns:
          masked_text: 플레이스홀더로 대체된 텍스트
          mapping:     플레이스홀더→원본 해시태그 매핑 사전
        """
        tags = self._extract_hashtags(text)
        mapping: Dict[str, str] = {}
        masked_text = text
        for idx, tag in enumerate(tags, start=1):
            placeholder = f"__HT_{idx}__"
            mapping[placeholder] = tag
            masked_text = masked_text.replace(tag, placeholder)
        return masked_text, mapping

    def _restore_placeholders(
        self,
        text: str,
        mapping: Dict[str, str]
    ) -> str:
        """
        플레이스홀더를 원본 해시태그로 복원
        """
        restored = text
        for placeholder, original in mapping.items():
            restored = restored.replace(placeholder, original)
        return restored

    def _force_restore_hashtags(
        self,
        original_text: str,
        translated_text: str
    ) -> str:
        """
        번역 과정 중 LLM이 해시태그 형식을 수정했을 경우
        원본 해시태그 순서를 기준으로 재삽입
        """
        orig_tags = self._extract_hashtags(original_text)
        idx = 0
        def replace_fn(match):
            nonlocal idx
            if idx < len(orig_tags):
                tag = orig_tags[idx]
                idx += 1
                return tag
            return match.group(0)
        return self._HT_PATTERN.sub(replace_fn, translated_text)

    # ─── 트윗 번역 처리 ─────────────────────────────────────────
    async def translate(
            self,
            tweet_text: str,
            tweet_timestamp: str
    )-> TranslationResult:
        """
        트윗 텍스트를 번역하고 LLM 분류 결과를 포함하여 반환

        과정:
          1) 해시태그 마스킹
          2) RAGService로부터 참조 문맥 획득
          3) 시스템 프롬프트 구성
          4) OpenAI chat completion 호출
          5) 결과 포맷 파싱(␞ 구분자)
          6) 플레이스홀더 역치환 및 해시태그 보강

        Args:
          tweet_text:     원본 트윗 텍스트
          tweet_timestamp: 트윗 작성 시각 ("YYYY-MM-DD HH:MM:SS")

        Returns:
          TranslationResult(번역문, 분류, 시작/종료 시간)
        """
        # 1) 해시태그 마스킹
        masked_text, ht_map = self._mask_hashtags(tweet_text)
        # 2) RAG 컨텍스트 로드
        contexts = self.rag.get_context(masked_text)
        logger.info("[LLMService] 최종 RAG 컨텍스트: %s", contexts)
        # 3) 시스템 프롬프트 준비
        system_prompt = SYSTEM_PROMPTS[PromptType.TRANSLATE].format(
            timestamp=tweet_timestamp
        )
        enriched_prompt = (
                system_prompt
                + "\n\n### Reference dictionary:\n"
                + "\n".join(f"- {c}" for c in contexts)
                + "\n\n"
        )
        # 4) OpenAI 호출
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": enriched_prompt},
                    {"role": "user", "content": masked_text.strip()},
                ],
                temperature=0.3,
            )
            raw_content = response.choices[0].message.content.strip()
            logger.debug("[LLMService] Raw response: %s", raw_content)
            # 5) 구분자(␞) 기반 파싱
            if raw_content.startswith("번역문"):
                raw_content = raw_content[len("번역문"):].lstrip()
            parts = [part.strip() for part in raw_content.split("␞", 3)]
            if len(parts) != 4:
                logger.warning(
                    "LLM 포맷 불일치: %s", parts
                )
                trans_masked = masked_text
                category = "일반"
                start_str = end_str = None
            else:
                trans_masked, category, start_str, end_str = parts
                start_str = None if start_str.lower() == "none" else start_str
                end_str = None if end_str.lower() == "none" else end_str
        except Exception as error:
            logger.error(
                "[LLMService] 번역 오류 발생, 기본값 사용: %s", error,
                exc_info=True
            )
            trans_masked = masked_text
            category = "일반"
            start_str = end_str = None
        # 6) 플레이스홀더 복원 및 해시태그 보강
        translated_text = self._restore_placeholders(trans_masked, ht_map)
        translated_text = self._force_restore_hashtags(tweet_text, translated_text)
        return TranslationResult(
            translated=translated_text,
            category=category,
            start=start_str,
            end=end_str,
        )

    # ─── 자동 리플라이 생성 ────────────────────────────────────────
    async def reply(self, tweet_text: str) -> ReplyResult:
        """
        주어진 트윗 텍스트에 대해 LLM을 사용해 자동 리플라이 문장을 생성
        """
        system_prompt = SYSTEM_PROMPTS[PromptType.REPLY]
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": tweet_text.strip()},
                ],
                temperature=0.5,
            )
            reply_msg = response.choices[0].message.content.strip()
            return ReplyResult(reply_text=reply_msg)
        except Exception as error:
            logger.error(
                "[LLMService] 자동 리플라이 생성 오류: %s", error,
                exc_info=True
            )
            raise