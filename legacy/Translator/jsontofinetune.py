import json
import os

#Designate File Directory Path
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "Dataset", "dataset.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "Dataset", "finetuneddataset.json")

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# GPT-3.5 Turbo Fine-tuning 형식에 맞게 변환
finetune_data = []
for dataset in data:
    korean_text = dataset.get("원문", "")
    japanese_text = dataset.get("최종번역문", "")

    if korean_text and japanese_text:
        finetune_data.append({
            "messages": [
                {"role": "system", "content": "다음 일본어 문장을 한국어로 번역하세요."},
                {"role": "user", "content": japanese_text},
                {"role": "assistant", "content": korean_text}
            ]
        })

# 변환이 완료된 데이터를 JSON 파일로 저장
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(finetune_data, f, ensure_ascii=False, indent=4)

print("Done")