from sentence_transformers import SentenceTransformer

_model = None
def get_embed_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model