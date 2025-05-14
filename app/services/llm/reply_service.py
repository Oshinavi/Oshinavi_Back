import logging

from openai import AsyncOpenAI

from app.services.llm.prompts import PromptType, SYSTEM_PROMPTS
from app.schemas.llm_schema import ReplyResult

logger = logging.getLogger(__name__)

class ReplyService:
    """
   자동 리플라이 생성 서비스 클래스
   - OpenAI API를 사용하여 주어진 트윗 텍스트에 대해
     팬으로서 자연스러운 일본어 응답을 생성
   """
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model_name: str = "gpt-4o-mini-2024-07-18"
    ):
        """
        Args:
          openai_client: OpenAI 비동기 클라이언트 인스턴스
          model_name:    사용할 OpenAI 모델 이름
        """
        self.openai = openai_client
        self.model  = model_name

    async def generate_reply(self, tweet_text: str) -> ReplyResult:
        """
        주어진 트윗 텍스트(tweet_text)에 대해 팬 페르소나의
        자연스러운 일본어 리플라이를 생성하여 반환

        과정:
          1) 시스템 프롬프트 설정 (팬 페르소나 부여)
          2) OpenAI ChatCompletion 호출
          3) 응답 메시지 추출 및 ReplyResult로 포장

        Args:
          tweet_text: 원본 트윗 텍스트

        Returns:
          ReplyResult: 생성된 리플라이 텍스트를 포함

        Raises:
          Exception: OpenAI 호출 실패 시 예외 재발생
                """
        system_prompt = SYSTEM_PROMPTS[PromptType.REPLY]
        try:
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": tweet_text.strip()},
                ],
                temperature=0.5,
            )
            reply_text = response.choices[0].message.content.strip()
            return ReplyResult(reply_text=reply_text)
        except Exception as error:
            logger.error(
                "[ReplyService] 자동 리플라이 생성 오류: %s", error,
                exc_info=True
            )
            raise