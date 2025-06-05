import json
import re

# ────────────────────────────────────────────────────────
# 1) 설정: 원본 JSONL 파일 경로와 출력 파일 경로
RAW_LOG_PATH = "twitter_dataset_new.jsonl"
OUTPUT_JSONL_PATH = "translations.jsonl"

# ────────────────────────────────────────────────────────
def parse_and_dump(raw_path: str, output_path: str):
    """
    raw_path: 원본 JSONL 파일 경로 (각 줄이 {"messages": [...]} 형태의 JSON)
    output_path: 변환된 JSONL을 저장할 파일명
    """
    records = []

    with open(raw_path, "r", encoding="utf-8") as fr:
        for line in fr:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # messages 배열의 첫 번째 요소가 user, 두 번째가 assistant
            msgs = obj.get("messages", [])
            if len(msgs) < 2:
                continue

            user_msg = msgs[0].get("content", "")
            assistant_msg = msgs[1].get("content", "")

            # 1) user_msg 안에서 "Tweet Text: " 이후의 원문 추출
            tweet_match = re.search(r"Tweet Text:\s*(.+)", user_msg)
            if tweet_match:
                source_text = tweet_match.group(1).strip()
            else:
                # 패턴이 없다면 건너뜀
                continue

            # 2) assistant_msg는 이미 "{\"Result\": \"...\", ...}" 식의 JSON 문자열 형태이므로 파싱
            try:
                parsed_assist = json.loads(assistant_msg)
                reference_text = parsed_assist.get("Result", "")
            except json.JSONDecodeError:
                reference_text = ""

            records.append({
                "source": source_text,
                "reference": reference_text
            })

    # ────────────────────────────────────────────────────────
    # 3) JSONL 파일로 한 줄씩 기록
    with open(output_path, "w", encoding="utf-8") as fw:
        for rec in records:
            fw.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"총 {len(records)}개의 레코드를 '{output_path}'에 저장했습니다.")

# ────────────────────────────────────────────────────────
if __name__ == "__main__":
    parse_and_dump(RAW_LOG_PATH, OUTPUT_JSONL_PATH)