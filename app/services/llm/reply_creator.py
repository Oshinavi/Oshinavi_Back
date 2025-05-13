# import os
# from openai import AsyncOpenAI
# from dotenv import load_dotenv
#
# SYSTEM_PROMPT_TEMPLATE = """
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
# api_key = os.getenv("OPENAI_API_KEY")
#
# client = AsyncOpenAI(api_key=api_key)
#
#
# async def generate_reply(tweet_text: str) -> str:
#     try:
#         response = await client.chat.completions.create(
#             model="gpt-4o-mini-2024-07-18",
#             messages=[
#                 {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
#                 {"role": "user", "content": tweet_text.strip()}
#             ],
#             temperature=0.5
#         )
#         return response.choices[0].message.content.strip()
#     except Exception as e:
#         return "リプライ生成に失敗しました。"
