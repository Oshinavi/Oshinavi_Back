import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
import re

# ChatGPT 일-한 번역 로직 정의

## 프롬프팅
SYSTEM_PROMPT_TEMPLATE = """
    You are an AI that processes Japanese tweets along with their timestamps.
    Tweet was posted on: {timestamp}

    Your tasks are:
    - Translate the tweet into Korean while keeping hashtags in their original Japanese form.
    - Identify whether the tweet is about one of the following categories: 일반, 방송, 라디오, 라이브, 음반, 굿즈, 영상, 게임.
    - ONLY IF the tweet explicitly includes a date or time:
        • an absolute date/time (e.g. '5/5(月) 20:30') or
        • a relative date immediately followed by a time (e.g. '今日20時') or
        • a “～まで” expression indicating an end bound (e.g. '今日まで', '明日まで')
        • a “～から” expression indicating a start bound (e.g. '明日15時から', '5/5 10:00から')
        • Extract it in the format 'YYYY.MM.DD HH:MM:SS'.  
        • To resolve relative dates like:
            – '明日' alone, only if paired with a time (e.g. '明日15時').
            – '~まで': treat as an **end date/time** at that day’s 23:59:59.
            – '～から': treat as a **start date/time** at the specified moment.
        • If only a start date/time is present, set the end date/time to exactly one hour after the start.
        • If only an end date/time is present, set the start date/time to that day at 00:00:00.
        • If both start and end date/times are present, use them as given.
      If no date/time information is present, output None for both.
    - If the tweet is not about 일반 or 굿즈, specify the related program, event, or media in Korean.
    - Do not add emojis that are not in the original text.

    Format your response exactly as:
      번역문 / 분류 / 시작 일자 / 종료 일자
"""

# .env 경로지정 및 openai api key 마운트
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "config", "settings.env")

load_dotenv(dotenv_path=ENV_PATH)
api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)

async def translate_japanese_tweet(tweet_text: str, tweet_timestamp: str) -> dict:
    """
    GPT에 전달 → "번역문 / 분류 / 시작 일자 / 종료 일자" 포맷을 반환
    """
    try:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(timestamp=tweet_timestamp)

        resp = await client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": tweet_text.strip()}
            ],
            temperature=0.3
        )

        # 원시 응답
        final_text = resp.choices[0].message.content.strip()
        print(f"🔍 Raw response: {final_text}")

        # "번역문 / 분류 / 시작 / 종료" 네 부분으로 분리
        parts = [p.strip() for p in re.split(r"\s*/\s*", final_text)]
        if len(parts) != 4:
            raise ValueError("응답 형식 오류: '번역문 / 분류 / 시작 일자 / 종료 일자' 네 개로 구분되어야 합니다.")

        translated, category, start_str, end_str = parts

        # None 처리
        start = None if start_str.lower() == "none" else start_str
        end   = None if end_str.lower()   == "none" else end_str

        # 파싱 결과 로그
        print("📌 Parsed fields:")
        print(f"   ▶ 번역문 : {translated}")
        print(f"   ▶ 분류   : {category}")
        print(f"   ▶ 시작일자: {start}")
        print(f"   ▶ 종료일자: {end}")

        return {
            "translated": translated,
            "category": category,
            "start": start,
            "end": end
        }

    except Exception as e:
        print(f"❗ 처리 중 오류 발생: {e}")
        return {
            "translated": None,
            "category": None,
            "start": None,
            "end": None,
            "error": str(e)
        }