import logging
from typing import List

from langchain_anthropic import ChatAnthropic
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain

from app.services.llm.prompt_templates import PromptType, SYSTEM_PROMPTS, get_few_shot_examples

logger = logging.getLogger(__name__)


def _build_system_prompt(prompt_type: PromptType, **kwargs) -> str:
    """
    few-shot 예시와 시스템 지침을 결합하여 완성된 system 프롬프트를 반환
    추가 매개변수가 필요할 경우 kwargs를 format에 사용
    """
    few = get_few_shot_examples(prompt_type)
    base = SYSTEM_PROMPTS[prompt_type].strip()
    if kwargs:
        base = base.format(**kwargs)
    return f"{few}\n\n{base}"


def _build_contexts(rag_service, text: str) -> str:
    """
    RAG 서비스로부터 컨텍스트를 받아 리스트 형식으로 문자열을 생성
    """
    contexts = rag_service.get_context(text)
    joined = "\n".join(f"- {c}" for c in contexts)
    logger.debug("RAG contexts for [%s]: %s", text, joined)
    return joined


class TranslationChain:
    """
    텍스트 번역을 위한 LLM 체인
    1) RAG 컨텍스트 생성
    2) 시스템 프롬프트 및 컨텍스트, 텍스트로 예측 수행
    """
    def __init__(self, rag_service, model_name: str = "claude-3-7-sonnet-20250219"):
        self.rag = rag_service
        self.llm = ChatAnthropic(
            model_name=model_name,
            timeout=120,
            temperature=0.3,
            stop=["\n\nHuman:"],
        )
        prompt = PromptTemplate(
            input_variables=["system", "contexts", "text"],
            template="""
<|system|>
{system}

### Reference dictionary:
{contexts}

<|user|>
{text}
""".strip(),
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="translation")

    def run(self, text: str, timestamp: str) -> str:
        system = _build_system_prompt(PromptType.TRANSLATE)
        contexts = _build_contexts(self.rag, text)
        return self.chain.predict(system=system, contexts=contexts, text=text)


class ClassificationChain:
    """
    텍스트 분류를 위한 LLM 체인
    1) RAG 컨텍스트 생성
    2) 시스템 프롬프트 및 컨텍스트, 텍스트로 예측 수행
    """
    def __init__(self, rag_service, model_name: str = "o4-mini-2025-04-16"):
        self.rag = rag_service
        self.llm = ChatOpenAI(model_name=model_name, temperature=1.0)
        prompt = PromptTemplate(
            input_variables=["system", "contexts", "text"],
            template="""
<|system|>
{system}

### Reference dictionary:
{contexts}

<|user|>
{text}
""".strip(),
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="category")

    def run(self, text: str) -> str:
        system = _build_system_prompt(PromptType.CLASSIFY)
        contexts = _build_contexts(self.rag, text)
        return self.chain.predict(system=system, contexts=contexts, text=text)


class ScheduleChain:
    """
    일정 추출을 위한 LLM 체인
    1) 시스템 프롬프트에 timestamp 포함
    2) 텍스트로 예측 수행
    """

    def __init__(self, model_name: str = "o4-mini-2025-04-16"):
        # o4-mini 모델은 temperature=1.0만 지원
        self.llm = ChatOpenAI(model_name=model_name, temperature=1.0)
        self.base_template = "{system}\n\n{text}"
        prompt = PromptTemplate(
            input_variables=["system", "text"],
            template=self.base_template,
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="schedule")

    def run(self, text: str, timestamp: str) -> str:
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"ScheduleChain 시작 - 입력 텍스트: {text}")
        logger.info(f"참조 타임스탬프: {timestamp}")

        system = _build_system_prompt(PromptType.SCHEDULE, timestamp=timestamp)

        # 프롬프트 로깅
        logger.debug(f"시스템 프롬프트 길이: {len(system)} 문자")

        # LLM 호출
        try:
            result = self.chain.predict(system=system, text=text)
            logger.info(f"ScheduleChain LLM 원본 응답: {result}")

            # 응답 파싱 : 디버깅 정보가 있다면 최종 답변만 추출
            if "␞" in result:
                lines = result.strip().split('\n')
                final_line = None

                # 최종 답변 라인 찾기 (ANALYSIS 등이 아닌 ␞가 포함된 라인)
                for line in lines:
                    line = line.strip()
                    if "␞" in line and not line.startswith(("ANALYSIS:", "TIMES FOUND:", "START:", "END:")):
                        final_line = line
                        break

                if final_line:
                    logger.info(f"파싱된 최종 결과: {final_line}")
                    return final_line
                else:
                    logger.warning("␞가 포함된 최종 답변을 찾을 수 없음")
                    # 첫 번째 ␞가 포함된 라인을 사용
                    for line in lines:
                        if "␞" in line:
                            logger.info(f"대체 결과 사용: {line.strip()}")
                            return line.strip()
                    return "None ␞ None"
            else:
                logger.warning(f"응답에 ␞ 구분자가 없음: {result}")
                return "None ␞ None"

        except Exception as e:
            logger.error(f"ScheduleChain 실행 중 오류: {e}")
            return "None ␞ None"


class ReplyChain:
    """
    자동 리플라이 생성을 위한 LLM 체인
    1) RAG 컨텍스트 생성(optional)
    2) 시스템 프롬프트 및 컨텍스트, 텍스트로 예측 수행
    """
    def __init__(self, model_name: str = "claude-3-5-haiku-20241022"):
        self.llm = ChatAnthropic(
            model_name=model_name,
            timeout=120,
            temperature=0.5,
            stop=["\n\nHuman:"],
        )
        prompt = PromptTemplate(
            input_variables=["system", "contexts", "text"],
            template="""
<|system|>
{system}

Existing replies (excluding the second one):
{contexts}

<|user|>
{text}
""".strip(),
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="reply")

    def run(self, text: str, contexts: List[str]) -> str:
        system = _build_system_prompt(PromptType.REPLY)
        # contexts를 리스트 그대로 전달 → 내부에서 PromptTemplate이 알아서 포맷
        joined = "\n".join(f"- {c}" for c in contexts)
        logger.debug("Reply contexts: %s", joined)
        return self.chain.predict(system=system, contexts=joined, text=text)