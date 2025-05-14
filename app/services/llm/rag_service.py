# app/services/llm/rag_service.py

import json
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from typing import List, Dict

class RAGService:
    def __init__(
        self,
        index_path: str,
        meta_path: str,
        top_k: int = 10,
        lexical_weight: float = 0.5,   # 단어 매칭 기반 검색 결과의 기여도 조정 하이퍼파라미터
    ):
        '''
        lexical_weight가 크면 BM25 기반 매칭을 더 강조하고, 작으면 embedding 유사도를 우선시함
        - 0.0에 가깝게 설정하면 semantic 검색 결과만 사용
        - 1.0 또는 그 이상으로 설정하면 BM25 기반 검색 결과의 영향력이 증가
        '''
        # 1) FAISS 인덱스 (semantic)
        self.index = faiss.read_index(index_path)

        # 2) 메타데이터 로드
        with open(meta_path, encoding="utf-8") as mf:
            self.metadata: List[Dict[str, str]] = json.load(mf)
        self.texts = [entry["text"] for entry in self.metadata]

        # 3) 임베더
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        # 4) BM25 인덱스 (lexical)
        tokenized_corpus = [t.split() for t in self.texts]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 5) 파라미터
        self.top_k = top_k
        self.lexical_weight = lexical_weight

    def get_context(self, query: str) -> List[str]:
        # — semantic 검색
        q_emb = self.embedder.encode([query])
        D, I = self.index.search(q_emb, self.top_k)
        sem_ids = [int(idx) for idx in I[0] if 0 <= idx < len(self.texts)]

        # — lexical 검색 (BM25) & list로 변환
        tokenized_q = query.split()
        bm25_scores = list(self.bm25.get_scores(tokenized_q))

        # 상위 top_k lexical id
        lex_ids = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[: self.top_k]

        # — union & 점수 결합
        combined_ids = set(sem_ids) | set(lex_ids)

        # semantic 거리 → 점수화
        max_dist = max(D[0]) if D.size else 1.0
        sem_score_map = {
            sem_ids[i]: (max_dist - D[0][i]) / max_dist
            for i in range(len(sem_ids))
        }

        # BM25 점수 정규화
        max_bm = max(bm25_scores) if bm25_scores else 1.0

        scored = []
        for idx in combined_ids:
            s_sem = sem_score_map.get(idx, 0.0)
            s_lex = (bm25_scores[idx] / max_bm) if max_bm > 0 else 0.0
            combined_score = s_sem + self.lexical_weight * s_lex
            scored.append((idx, combined_score))

        # 최종 정렬 및 상위 top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        final_ids = [idx for idx, _ in scored[: self.top_k]]

        # “원문 → 번역” 포맷으로 반환
        return [
            f"{self.metadata[i]['text']} → {self.metadata[i]['translation']}"
            for i in final_ids
        ]