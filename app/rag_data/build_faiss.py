import csv, json
from sentence_transformers import SentenceTransformer
import faiss
from pathlib import Path
import numpy as np

# ─── 상수 정의 ─────────────────────────────────────────────────────
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

BASE_DIR = Path(__file__).resolve().parent
DICT_CSV = BASE_DIR / "dict.csv"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
INDEX_FILE_PATH = VECTOR_STORE_DIR / "faiss_index.bin"
METADATA_FILE_PATH = VECTOR_STORE_DIR / "metadata.json"

def build_faiss_index() -> None:
    """
    FAISS 인덱스를 생성하고 메타데이터를 저장

    1) dict.csv에서 일본어 용어 및 한국어 번역 데이터 로드
    2) SentenceTransformer로 임베딩 생성 후 정규화
    3) FAISS FlatIP 인덱스 구축 및 파일로 저장
    4) 메타데이터(JSON)로 용어-번역 쌍 저장
    """

    # 출력 디렉토리 생성
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

    # SentenceTransformer 모델 로드
    embedding_model = SentenceTransformer(MODEL_NAME)

    source_terms: list[str] = []
    target_translations: list[str] = []
    with open(DICT_CSV, encoding="utf-8") as f:
        for ja, ko in csv.reader(f):
            source_terms.append(ja)
            target_translations.append(ko)

    # 문장 임베딩 생성 (배치 진행 상황 표시)
    embeddings = embedding_model.encode(
        source_terms,
        show_progress_bar=True
    )
    # L2 Norm
    faiss.normalize_L2(embeddings)

    # ── FAISS 인덱스 생성 및 저장 ─────────────────────────────────
    faiss_index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
    num_embeddings = embeddings.shape[0]
    embeddings = embeddings.astype(np.float32)
    faiss_index.add(n=num_embeddings, x=embeddings)
    faiss.write_index(faiss_index, str(INDEX_FILE_PATH))

    # ── 메타데이터 생성 및 저장 ────────────────────────────────────
    metadata_entries = [
        {"text": source_terms[i], "translation": target_translations[i]}
        for i in range(len(source_terms))
    ]
    with open(METADATA_FILE_PATH, "w", encoding="utf-8") as mf:
        json_text = json.dumps(metadata_entries, ensure_ascii=False, indent=2)
        mf.write(json_text)

if __name__ == "__main__":
    build_faiss_index()
    print(f"FAISS 인덱스 및 메타데이터 생성 완료:\n  - Index: {INDEX_FILE_PATH}\n  - Metadata: {METADATA_FILE_PATH}")
