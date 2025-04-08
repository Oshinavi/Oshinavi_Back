import openai
from openai import AsyncOpenAI
from datetime import datetime, timedelta

openai.api_key = "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"

SYSTEM_PROMPT_TEMPLATE = """
You are an AI that processes Japanese tweets along with their timestamps.
Tweet was posted on: {timestamp}

Your tasks are:
- Translate the tweet into Korean while keeping hashtags in their original Japanese form.
- Identify whether the tweet is about General, Broadcast, Radio, Live, Goods, Video, or Game.
- ONLY IF the tweet explicitly includes a date or time (either absolute or relative like '오늘', '내일', '3시'), extract it in the format 'YYYY.MM.DD HH:MM:SS'.
- To resolve relative dates like '내일', use the tweet timestamp.
- If the tweet is not about General or Goods, specify the related program, event, or media in Korean.
- Do not add emojis that are not in the original text.

Format your response as: 번역문 / 분류 / 날짜정보 또는 None
"""

client = AsyncOpenAI(api_key="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")  # 기존 openai.api_key 설정 대신 객체 생성

async def translate_japanese_tweet(tweet_text: str, tweet_timestamp: str) -> dict:
    try:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(timestamp=tweet_timestamp)

        response = await client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": tweet_text.strip()}
            ],
            temperature=0.3
        )

        result = response.choices[0].message.content.strip()
        print(f"🔍 Raw response: {result}")

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
        print(f"❌ 처리 중 오류 발생: {e}")
        return {
            "translated": None,
            "category": None,
            "datetime": None,
            "error": str(e)
        }


def convert_twitter_timestamp_to_kst(twitter_time: str) -> str:
    utc_dt = datetime.strptime(twitter_time, "%a %b %d %H:%M:%S %z %Y")
    kst_dt = utc_dt + timedelta(hours=9)
    return kst_dt.strftime("%Y-%m-%d %H:%M:%S")


# # ✅ 테스트 실행용 코드
# if __name__ == "__main__":
#     tweet_text = """本日20時よりMVがプレミア公開🎶 わたしも初めてみるので楽しみです🤍 #アイドルの養育費"""
#     tweet_timestamp_raw = "Wed Jan 08 10:08:57 +0000 2025"
#     tweet_timestamp_kst = convert_twitter_timestamp_to_kst(tweet_timestamp_raw)
#
#     print(f"📅 변환된 KST 타임스탬프: {tweet_timestamp_kst}")
#
#     async def test():
#         result = await translate_japanese_tweet(tweet_text, tweet_timestamp_kst)
#         print("✅ 결과:")
#         print(result)
#
#     asyncio.run(test())