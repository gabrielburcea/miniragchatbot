"""
Local embedding provider usign sentence-transformers library.

Model of choice is BAAW/bge-small-en-v1.5 (configured in app/config.py) - free, furns on
CPU, aprox 130 MB download on first use, 384-dimensional output vectors

"""
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.config import settings

# loading (only once per process not on every function call) the sentence-transformers model from disk takes a few second
@lru_cache(maxsize=1)

def _get_model() -> SentenceTransformer:
    """
    Get the sentence-transformers model instance.

    Returns:
        SentenceTransformer: The loaded sentence-transformers model.
    """
    return SentenceTransformer(settings.embedding_model)

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of text (e.g. chuncks) into vectors
    """
    if not texts:
        return []
    model = _get_model()
    # normalize_embeddings=True ensures that the output vectors are normalized to unit length, which is often useful for similarity calculations.
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()

def embed_query(text: str) -> list[float]:
    """
    Embed a single query text into a vector
    """
    return embed_texts([text])[0]

