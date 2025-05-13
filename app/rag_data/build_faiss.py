# app/rag_data/build_faiss.py

import csv, json
from sentence_transformers import SentenceTransformer
import faiss
from pathlib import Path

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMB_DIM    = 384

BASE_DIR   = Path(__file__).resolve().parent
DICT_CSV   = BASE_DIR / "dict.csv"
OUT_DIR    = BASE_DIR / "vector_store"
INDEX_PATH = OUT_DIR / "faiss_index.bin"
META_PATH  = OUT_DIR / "metadata.json"

def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    model = SentenceTransformer(MODEL_NAME)
    terms, translations = [], []
    with open(DICT_CSV, encoding="utf-8") as f:
        for ja, ko in csv.reader(f):
            terms.append(ja)
            translations.append(ko)

    embeddings = model.encode(terms, show_progress_bar=True)
    faiss.normalize_L2(embeddings)

    # 1) FAISS 인덱스 생성
    index = faiss.IndexFlatIP(EMB_DIM)
    index.add(embeddings)
    faiss.write_index(index, str(INDEX_PATH))

    # 2) 메타데이터를 "리스트 of dict" 로 저장
    meta = [
        {"text": terms[i], "translation": translations[i]}
        for i in range(len(terms))
    ]
    with open(META_PATH, "w", encoding="utf-8") as mf:
        json.dump(meta, mf, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    build()
    print(f"✅ built: {INDEX_PATH} + {META_PATH}")