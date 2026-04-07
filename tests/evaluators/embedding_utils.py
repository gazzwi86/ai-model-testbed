"""Shared embedding utilities for evaluators and voting.

Provides a cached SentenceTransformer model, cosine similarity,
and batch embedding helpers.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

_model_cache: dict = {}


def get_model(model_name: str = "all-MiniLM-L6-v2"):
    """Get or create a cached SentenceTransformer model."""
    if model_name not in _model_cache:
        try:
            from sentence_transformers import SentenceTransformer
            _model_cache[model_name] = SentenceTransformer(model_name)
        except ImportError:
            logger.error("sentence-transformers not installed")
            raise
    return _model_cache[model_name]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embed_texts(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    """Embed a list of texts using the cached model."""
    model = get_model(model_name)
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
