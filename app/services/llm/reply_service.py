import logging

from openai import AsyncOpenAI

from app.services.llm.prompts import PromptType, SYSTEM_PROMPTS
from app.schemas.llm_schema import ReplyResult

logger = logging.getLogger(__name__)

class ReplyService:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model: str = "gpt-4o-mini-2024-07-18"
    ):
        self.openai = openai_client
        self.model  = model

    async def generate_reply(self, tweet_text: str) -> ReplyResult:
        system = SYSTEM_PROMPTS[PromptType.REPLY]
        try:
            resp = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": tweet_text.strip()},
                ],
                temperature=0.5
            )
            return ReplyResult(reply_text=resp.choices[0].message.content.strip())
        except Exception as e:
            logger.error("LLM reply error", exc_info=e)
            raise


# import os
# from dotenv import load_dotenv
# from app.utils.ollama_client import OllamaClient
#
# SYSTEM_PROMPT = """
# あなたは、アイドルのファンとして、X（旧Twitter）でリプライを送るAIです。
# 相手は日本の女性アイドルで、日常の投稿やお知らせ（放送・ライブ・グッズなど）をXに投稿しています。
#
# あなたの役割は、ファンとして自然で丁寧な日本語でリプライを送ることです。
#
# 次のルールに従ってください：
# - 投稿内容が日常的な挨拶（例：おはよう、こんにちは）なら、同じような挨拶＋応援の気持ちを込めた一言を返してください。
# - 投稿が活動に関するお知らせ（例：放送、ライブ、グッズ発売）なら、「楽しみにしています」「応援しています」「遠くからでも見守ってます」などの応援メッセージを添えてください。
# - ファンとしての立場を守り、アイドルに失礼のないように丁寧な言葉を使ってください。
# - 絵文字はあっても1〜2個まで。無理に使う必要はありません。
# - 必ず日本語で返答してください。
# - 生成される返信の文字数は最大560バイトまでにしてください。
# """
#
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ENV_PATH = os.path.join(BASE_DIR, "config", "settings.env")
# load_dotenv(dotenv_path=ENV_PATH)
# OLLAMA_API_URL = os.getenv("OLLAMA_API_URL")
# OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL")
#
# ollama = OllamaClient(OLLAMA_API_URL, OLLAMA_MODEL)
#
#
# async def generate_reply(tweet_text: str) -> str:
#     messages = [
#         {"role": "system",  "content": SYSTEM_PROMPT},
#         {"role": "user",    "content": tweet_text.strip()}
#     ]
#     try:
#         return await ollama.chat(messages, temperature=0.5)
#     except Exception:
#         return "リプライ生成に失敗しました。"