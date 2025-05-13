# import re
# from openai import AsyncOpenAI
# from typing import Optional, Dict
# from app.core.config import settings
# import logging
#
# logger = logging.getLogger(__name__)
#
# SYSTEM_PROMPT_TEMPLATE = """
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
# client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
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
#
#     try:
#         system_prompt = SYSTEM_PROMPT_TEMPLATE.format(timestamp=tweet_timestamp)
#
#         response = await client.chat.completions.create(
#             model="gpt-4o-mini-2024-07-18",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": tweet_text.strip()}
#             ],
#             temperature=0.3
#         )
#
#         result = response.choices[0].message.content.strip()
#         logger.info(f"🔍 GPT 응답: {result}")
#
#         # 응답 포맷 확인 및 분리
#         parts = [p.strip() for p in re.split(r"\s*/\s*", result)]
#         if len(parts) != 4:
#             raise ValueError("응답 형식 오류: '번역문 / 분류 / 시작 일자 / 종료 일자'")
#
#         translated, category, start_raw, end_raw = parts
#
#         return {
#             "translated": translated,
#             "category": category,
#             "start": None if start_raw.lower() == "none" else start_raw,
#             "end": None if end_raw.lower() == "none" else end_raw
#         }
#
#     except Exception as e:
#         logger.error(f"❗ GPT 번역 오류: {e}")
#         return {
#             "translated": None,
#             "category": None,
#             "start": None,
#             "end": None,
#             "error": str(e)
#         }