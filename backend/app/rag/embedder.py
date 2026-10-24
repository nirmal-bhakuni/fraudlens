"""Local text embeddings (sentence-transformers). No API key, no network after the first download."""
from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def get_model():
    # Imported here so the app and the tests do not load torch unless they need it.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed(texts: list[str]) -> list[list[float]]:
    """One 384-number vector per text. Vectors are normalized (length 1)."""
    vectors = get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()