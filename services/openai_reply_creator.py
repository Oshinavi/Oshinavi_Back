import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

SYSTEM_PROMPT_TEMPLATE = """
あなたは、アイドルのファンとして、X（旧Twitter）でリプライを送るAIです。
相手は日本の女性アイドルで、日常の投稿やお知らせ（放送・ライブ・グッズなど）をXに投稿しています。

あなたの役割は、ファンとして自然で丁寧な日本語でリプライを送ることです。

次のルールに従ってください：
- 投稿内容が日常的な挨拶（例：おはよう、こんにちは）なら、同じような挨拶＋応援の気持ちを込めた一言を返してください。
- 投稿が活動に関するお知らせ（例：放送、ライブ、グッズ発売）なら、「楽しみにしています」「応援しています」「遠くからでも見守ってます」などの応援メッセージを添えてください。
- ファンとしての立場を守り、アイドルに失礼のないように丁寧な言葉を使ってください。
- 絵文字はあっても1〜2個まで。無理に使う必要はありません。
- 必ず日本語で返答してください。
- 生成される返信の文字数は最大280バイトまでにしてください。
"""


# .env 경로지정 및 openai api key 마운트
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "config", "settings.env")
load_dotenv(dotenv_path=ENV_PATH)
api_key = os.getenv("OPENAI_API_KEY")

# OpenAI 클라이언트
client = AsyncOpenAI(api_key=api_key)


async def reply_generator(tweet_text: str) -> str:
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": tweet_text.strip()}
            ],
            temperature=0.5
        )

        reply_text = response.choices[0].message.content.strip()
        print(f"생성된 리플라이: {reply_text}")
        return reply_text

    except Exception as e:
        print(f"오류 발생: {e}")
        return "리플라이 생성에 실패했습니다."

# async def test_reply_generation():
#     # 실제 테스트용 트윗 (일본어)
#     test_tweets = [
#         "🌱フォロワー　30000人🌱ありがとうございます…!! しかもデビュー1周年のタイミングで、もう一つお祝い事が増えてとても嬉しいです🥰 「葉山風花」のことをもっとたくさんの方に知っていただけるように、これからも尽力して参ります！ 引き続きよろしくお願いいたします！",
#         "105期がスタートしました🪷 私は変わらず小鈴ちゃんのすぐそばで、小鈴ちゃんを守り、一緒に成長できたらと思っております！ 蓮ノ空女学院スクールアイドルクラブでの活動を引き続き応援していただけますと幸いです。 よろしくお願いいたします！",
#     ]
#
#     for tweet in test_tweets:
#         print(f"\n📝 アイドルのツイート: {tweet}")
#         reply = await reply_generator(tweet)
#         print(f"💬 ファンのリプライ: {reply}")
#
# # 비동기 실행
# if __name__ == "__main__":
#     asyncio.run(test_reply_generation())