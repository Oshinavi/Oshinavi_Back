import json
from typing import List, Dict, Tuple

import faiss
from rank_bm25 import BM25Okapi
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
        top_k: int = 10,
        lexical_weight: float = 0.5,   # 단어 매칭 기반 검색 결과의 기여도 조정 하이퍼파라미터
    ):
        """
        Args:
          index_path:       FAISS 인덱스 파일 경로
          meta_path:        JSON 메타데이터 파일 경로
          top_k:            반환할 컨텍스트 최대 개수
          lexical_weight:   BM25(Lexical) 점수 가중치(semantic 점수와 합산)

        lexical_weight 값이 0.0에 가까우면 의미 기반 검색 우선,
        1.0 이상이면 BM25 lexical 검색 영향력 증가
        """
        # 1) FAISS 인덱스 로드 (semantic retrieval)
        self.index = faiss.read_index(index_path)

        # 2) 메타데이터 로드
        with open(meta_path, encoding="utf-8") as f:
            self.metadata: List[Dict[str, str]] = json.load(f)
        self.source_texts = [entry["text"] for entry in self.metadata]

        # 3) 임베딩 모델 초기화
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        # 4) BM25 인덱스 초기화 (lexical retrieval)
        tokenized_corpus = [text.split() for text in self.source_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 5) RAG 파라미터 저장
        self.top_k = top_k
        self.lexical_weight = lexical_weight


    def get_context(self, query: str) -> List[str]:
        """
        주어진 쿼리에 대해 semantic + lexical 검색을 결합하여
        상위 top_k개의 "원문 → 번역" 컨텍스트 목록을 반환
        """

        # 1) Semantic 검색: FAISS 유사도 검색
        query_embedding = self.embedder.encode([query])
        distances, indices = self.index.search(query_embedding, self.top_k)
        semantic_indices = [int(i) for i in indices[0] if 0 <= i < len(self.source_texts)]

        # 2) Lexical 검색: BM25 점수 계산
        tokenized_query = query.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_lex_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[: self.top_k]

        # 3) ID 합집합 및 점수 결합
        candidate_indices = set(semantic_indices) | set(top_lex_indices)

        # Semantic distance → 유사도 점수화
        max_distance = max(distances[0]) if distances.size else 1.0
        sem_score_map = {
            semantic_indices[i]: (max_distance - distances[0][i]) / max_distance
            for i in range(len(semantic_indices))
        }

        # BM25 점수 정규화
        max_bm25 = max(bm25_scores) if bm25_scores else 1.0

        combined_scores: List[Tuple[int, float]] = []
        for idx in candidate_indices:
            sem_score = sem_score_map.get(idx, 0.0)
            lex_score = (bm25_scores[idx] / max_bm25) if max_bm25 > 0 else 0.0
            total_score = sem_score + self.lexical_weight * lex_score
            combined_scores.append((idx, total_score))

        # 4) 점수 내림차순 정렬 및 상위 top_k 선택
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        selected_indices = [idx for idx, _ in combined_scores[: self.top_k]]

        # 5) "원문 → 번역" 형식으로 컨텍스트 리스트 반환
        contexts = [
            f"{self.metadata[i]['text']} → {self.metadata[i]['translation']}"
            for i in selected_indices
        ]
        return contexts
