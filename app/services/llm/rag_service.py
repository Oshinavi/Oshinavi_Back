import faiss
import json
from sentence_transformers import SentenceTransformer
from typing import List, Tuple

class RAGService:
    def __init__(
        self,
        index_path: str,
        meta_path: str,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        top_k: int = 5
    ):
        # 1) FAISS 인덱스
        self.index = faiss.read_index(index_path)
        # 2) 메타데이터 (CSV 대신 미리 JSON으로 준비)
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)  # [{ "id":0, "text":"蓮ノ空,하스노소라"}, …]
        # 3) 임베딩 모델
        self.embedder = SentenceTransformer(embedding_model_name)
        self.top_k = top_k

    def get_context(self, query: str) -> List[str]:
        q_emb = self.embedder.encode([query])
        D, I = self.index.search(q_emb, self.top_k)
        docs: List[str] = []
        for idx in I[0]:
            if idx < len(self.metadata):
                docs.append(self.metadata[idx]["text"])
        return docs