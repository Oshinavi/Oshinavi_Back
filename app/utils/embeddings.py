from sentence_transformers import SentenceTransformer

_embed_model: SentenceTransformer | None = None

def get_sentence_embedding_model() -> SentenceTransformer:
    """
    전역 싱글톤으로 SentenceTransformer 모델을 로드하여 반환
    - 최초 호출 시에만 모델을 로드하고 이후에는 캐시된 인스턴스 재사용
    """
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model