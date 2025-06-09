import json
from typing import List, Dict, Tuple

import faiss
from rank_bm25 import BM25Okapi
from fugashi import Tagger
from sentence_transformers import SentenceTransformer

class RAGService:
    """
    RAG(검색 증강 생성) 서비스 클래스
    - FAISS 임베딩 검색(semantic)과 BM25 lexical 검색을 결합하여
      질의와 유사한 문장-번역 쌍(context) 목록을 반환
    """
    def __init__(
        self,
        index_path: str,
        meta_path: str,
        top_k: int = 15,
        lexical_weight: float = 0.7,
    ):
        # 1) FAISS 인덱스 로드 (semantic retrieval)
        self.index = faiss.read_index(index_path)

        # 2) 메타데이터 로드
        with open(meta_path, encoding="utf-8") as f:
            self.metadata: List[Dict[str, str]] = json.load(f)
        self.source_texts = [entry["text"] for entry in self.metadata]

        # 3) 임베딩 모델 초기화
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        # 4) 형태소 분석기 초기화
        self.tagger = Tagger()

        # 5) BM25 인덱스 초기화
        tokenized_corpus = [self._tokenize(text) for text in self.source_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 6) RAG 파라미터 저장
        self.top_k = top_k
        self.lexical_weight = lexical_weight

    def _tokenize(self, text: str) -> List[str]:
        """
        일본어 형태소 단위로 토큰화
        """
        return [word.surface for word in self.tagger(text)]

    def get_context(self, query: str) -> List[str]:
        """
        주어진 쿼리에 대해 semantic + lexical 검색을 결합하여 상위 top_k개의 "원문 → 번역" 컨텍스트 목록을 반환
        """
        # 1) Semantic 검색: FAISS cosine similarity 검색
        query_embedding = self.embedder.encode([query])
        sims, indices = self.index.search(query_embedding, self.top_k)
        sims = sims[0]  # inner-product 값 == cosine similarity (L2-normalized vectors)
        semantic_indices = [int(i) for i in indices[0] if 0 <= i < len(self.source_texts)]

        # 2) Lexical 검색: BM25 점수 계산
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_lex_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[: self.top_k]

        # 3) 후보 인덱스 집합
        candidate_indices = set(semantic_indices) | set(top_lex_indices)

        # 4) Semantic similarity 정규화
        max_sim = float(sims.max()) if sims.size > 0 else 1.0
        sem_score_map: Dict[int, float] = {
            semantic_indices[i]: sims[i] / max_sim
            for i in range(len(semantic_indices))
        }

        # 5) BM25 점수 정규화
        max_bm = float(bm25_scores.max()) if bm25_scores.size > 0 else 1.0

        # 6) combined score 계산
        combined_scores: List[Tuple[int, float]] = []
        for idx in candidate_indices:
            sem_sc = sem_score_map.get(idx, 0.0)
            lex_sc = (bm25_scores[idx] / max_bm) if max_bm > 0 else 0.0
            total_sc = sem_sc + self.lexical_weight * lex_sc
            combined_scores.append((idx, total_sc))

        # 7) 상위 top_k 선택
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        selected = [idx for idx, _ in combined_scores[: self.top_k]]

        # 8) “원문 → 번역” 컨텍스트 반환
        return [
            f"{self.metadata[i]['text']} → {self.metadata[i]['translation']}"
            for i in selected
        ]