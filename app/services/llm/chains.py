# app/services/llm/chains.py

import logging
from app.services.llm.prompt_templates import PromptType, SYSTEM_PROMPTS, get_few_shot_examples
from langchain_anthropic import ChatAnthropic
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class TranslationChain:
    def __init__(self, rag_service, model_name: str = "claude-3-7-sonnet-20250219"):
        self.rag = rag_service
        self.llm = ChatAnthropic(
            stop=["\n\nHuman:"],
            timeout=120,
            model_name=model_name,
            temperature=0.3,
        )

        # few-shot + 시스템 프롬프트 결합
        few = get_few_shot_examples(PromptType.TRANSLATE)
        system_all = f"""{few}

{SYSTEM_PROMPTS[PromptType.TRANSLATE]}"""

        # PromptTemplate 에 system, contexts, text 모두 전달
        prompt = PromptTemplate(
            input_variables=["system", "contexts", "text"],
            template="""
<|system|>
{system}

### Reference dictionary:
{contexts}

<|user|>
{text}
""".strip()
        )
        self.chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            output_key="translation",
        )

    def run(self, text: str, timestamp: str) -> str:
        # RAG로 컨텍스트 생성
        contexts = "\n".join(f"- {c}" for c in self.rag.get_context(text))
        logger.info("RAG contexts for text [%s]:\n%s", text, contexts)

        # 시스템 메시지(few-shot + 지침)를 이 시점에 완성
        few = get_few_shot_examples(PromptType.TRANSLATE)
        system_all = f"""{few}

{SYSTEM_PROMPTS[PromptType.TRANSLATE]}"""

        # 실제 번역 수행 (system, contexts, text 모두 전달)
        return self.chain.predict(
            system=system_all,
            contexts=contexts,
            text=text
        )

class ClassificationChain:
    def __init__(self, rag_service, model_name: str = "gpt-4-0613"):
        self.llm = ChatOpenAI(model_name=model_name)
        self.rag = rag_service

        few = get_few_shot_examples(PromptType.CLASSIFY)
        system_all = f"""{few}

{SYSTEM_PROMPTS[PromptType.CLASSIFY].strip()}"""

        prompt = PromptTemplate(
            input_variables=["system", "contexts", "text"],
            template="""
        <|system|>
        {system}

        ### Reference dictionary:
        {contexts}

        <|user|>
        {text}
        """.strip()
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="category")

    def run(self, text: str) -> str:
        contexts = "\n".join(f"- {c}" for c in self.rag.get_context(text))
        logging.info("RAG contexts for classify [%s]:\n%s", text, contexts)
        few = get_few_shot_examples(PromptType.CLASSIFY)
        system_all = f"{few}\n\n{SYSTEM_PROMPTS[PromptType.CLASSIFY].strip()}"
        return self.chain.predict(
            system=system_all,
            contexts=contexts,
            text=text)


class ScheduleChain:
    def __init__(self, model_name: str = "gpt-4-0613"):
        self.llm = ChatOpenAI(model_name=model_name)

        # few-shot 예시만 미리 불러 두고
        self.few = get_few_shot_examples(PromptType.SCHEDULE)

        # 입력 변수는 text 하나만
        self.base_template = """{system}

{text}
"""
        self.chain = LLMChain(
            llm=self.llm,
            prompt=PromptTemplate(
                input_variables=["system", "text"],
                template=self.base_template
            ),
            output_key="schedule"
        )

    def run(self, text: str, timestamp: str) -> str:
        # timestamp 를 치환한 시스템 프롬프트를 이 시점에 완성
        sched_prompt = SYSTEM_PROMPTS[PromptType.SCHEDULE].format(timestamp=timestamp)
        system_all = f"""{self.few}

{sched_prompt}"""
        # PromptTemplate 업데이트
        self.chain.prompt = PromptTemplate(
            input_variables=["system", "text"],
            template=f"""{system_all}

{{text}}
"""
        )
        # 이제 predict 에 system 과 text를 모두 넘깁니다.
        return self.chain.predict(system=system_all, text=text)


class ReplyChain:
    def __init__(self, model_name: str = "claude-3-5-haiku-20241022"):
        self.llm = ChatAnthropic(
            stop=["\n\nHuman:"],
            timeout=120,
            model_name=model_name,
            temperature=0.5,
        )

        few = get_few_shot_examples(PromptType.REPLY)
        system_all = f"""{few}

{SYSTEM_PROMPTS[PromptType.REPLY].strip()}"""

        prompt = PromptTemplate(
            input_variables=["system", "text"],
            template="""
<|system|>
{system}

<|user|>
{text}
""".strip(),
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="reply")

    def run(self, text: str) -> str:
        few = get_few_shot_examples(PromptType.REPLY)
        system_all = f"{few}\n\n{SYSTEM_PROMPTS[PromptType.REPLY].strip()}"
        return self.chain.predict(system=system_all, text=text)