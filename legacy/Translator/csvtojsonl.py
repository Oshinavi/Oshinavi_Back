import pandas as pd
import json

DATAPATH_CSV = "../csv/dataset_fuka.csv"
DATAPATH_JSONL = "../Dataset/twitter_dataset.jsonl"


def csv_to_jsonl(csv_file, jsonl_file):
    system_prompt = """
    You are an AI that processes Japanese tweets along with their timestamps.
    Your tasks are:
    - Translate the tweet into Korean while keeping hashtags in their original Japanese form.
    - Identify whether the tweet is about General, Broadcast, Radio, Live, Goods, Video, or Game.
    - If the tweet is about Broadcast, Radio, Live, or Video and includes a date/time, extract it in the format 'YYYY.MM.DD HH:MM:SS'.
    - If the tweet is not about General or Goods, specify the exact related program, event, or media in Korean.
    - Do not add emojis that are not in the original text.
    - If unsure, refer to the web for additional context.
    """

    df = pd.read_csv(csv_file)

    with open(jsonl_file, 'w', encoding='utf-8') as f:
        # Write system prompt as the first entry
        f.write(
            json.dumps({"messages": [{"role": "system", "content": system_prompt.strip()}]}, ensure_ascii=False) + "\n")

        for _, row in df.iterrows():
            # 빈 문자열을 null(None)로 변환
            row = row.where(pd.notna(row), None)

            json_obj = {
                "messages": [
                    {"role": "user", "content": f"Created At: {row['Created At']}\nTweet Text: {row['Tweet Text']}"},
                    {"role": "assistant", "content": json.dumps({
                        "Result": row["Result"],
                        "Attribute": row["Attribute"],
                        "Schedule Info": row["Schedule Info"],
                        "Time": row["Time"]
                    }, ensure_ascii=False)}
                ]
            }
            f.write(json.dumps(json_obj, ensure_ascii=False) + "\n")


# Usage example
csv_to_jsonl(DATAPATH_CSV, DATAPATH_JSONL)
