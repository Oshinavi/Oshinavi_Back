import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

# ChatGPT 일-한 번역 로직 정의


## 프롬프팅

SYSTEM_PROMPT_TEMPLATE = """
You are an AI that processes Japanese tweets along with their timestamps.
Tweet was posted on: {timestamp}

Your tasks are:
- Translate the tweet into Korean while keeping hashtags in their original Japanese form.
- Identify whether the tweet is about General, Broadcast, Radio, Live, Goods, Video, or Game.
- ONLY IF the tweet explicitly includes a date or time (either absolute or relative like '今日', '明日', '3時'), extract it in the format 'YYYY.MM.DD HH:MM:SS'.
- To resolve relative dates like '明日', use the tweet timestamp.
- If the tweet is not about General or Goods, specify the related program, event, or media in Korean.
- Do not add emojis that are not in the original text.

Format your response as: 번역문 / 분류 / 날짜정보 또는 None
"""

# .env 경로지정 및 openai api key 마운트
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "config", "settings.env")

load_dotenv(dotenv_path=ENV_PATH)
api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)

async def translate_japanese_tweet(tweet_text: str, tweet_timestamp: str) -> dict:
    try:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(timestamp=tweet_timestamp)

        ## 모델 및 프롬프트 지정
        response = await client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": tweet_text.strip()}
            ],
            temperature=0.3 ## 결과값 변화 정도
        )

        result = response.choices[0].message.content.strip()
        print(f"🔍 Raw response: {result}")

        ## 걀과값 파싱
        parts = [p.strip() for p in result.split(" / ")]
        if len(parts) < 2:
            raise ValueError("응답 형식이 올바르지 않습니다. ' / ' 로 구분된 3개 항목이 필요합니다.")

        translated = parts[0]
        category = parts[1]
        datetime_info = parts[2] if len(parts) > 2 and parts[2].lower() != "none" else None

        return {
            "translated": translated,
            "category": category,
            "datetime": datetime_info
        }

    except Exception as e:
        print(f"처리 중 오류 발생: {e}")
        return {
            "translated": None,
            "category": None,
            "datetime": None,
            "error": str(e)
        }