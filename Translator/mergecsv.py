import pandas as pd
import random
import glob

DATASET_PATH = "../csv/dataset.csv"

# n개의 CSV 파일 가져오기
csv_files = glob.glob("../csv/*.csv")  # 원하는 폴더 경로 설정

# 결과를 저장할 리스트
dataset = []

# 각 CSV 파일에서 랜덤하게 100개 행 샘플링
for file in csv_files:
    df = pd.read_csv(file)
    filtered_df = df[~df["Tweet Text"].str.contains("RT @", na=False)]  # "RT @" 포함된 행 제거

    if len(filtered_df) >= 100:
        sampled_df = filtered_df.sample(n=100, random_state=random.randint(0, 10000))  # 랜덤 샘플링
    else:
        sampled_df = filtered_df  # 부족하면 가능한 만큼 저장

    dataset.append(sampled_df)

# 모든 데이터를 하나의 DataFrame으로 합치기
final_dataset = pd.concat(dataset, ignore_index=True)

# 결과를 CSV 파일로 저장
final_dataset.to_csv(DATASET_PATH, index=False)

print(f"총 {len(csv_files)}개의 파일에서 샘플링하여 dataset.csv에 저장 완료.")
