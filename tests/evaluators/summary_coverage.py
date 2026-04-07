"""Summary coverage evaluator.

Compares a model-generated summary against gold-standard key points
using sentence-transformer embeddings and cosine similarity.

Returns:
    {
        "key_point_coverage": float,
        "factual_accuracy": float | None,
        "hallucination_rate": float | None,
        "concision": float,
    }

All percentages are in [0.0, 100.0].
factual_accuracy and hallucination_rate are placeholders for the LLM judge.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Cosine similarity threshold for considering a gold key-point "covered".
_COVERAGE_THRESHOLD = 0.5

from .embedding_utils import cosine_similarity as _cosine_similarity, embed_texts as _embed_texts


# ---------------------------------------------------------------------------
# Gold-standard loading
# ---------------------------------------------------------------------------

def load_gold_key_points(gold_path: str) -> list[str]:
    """Load a gold-standard key-points JSON file.

    Expects a JSON array of strings.
    """
    path = Path(gold_path)
    if not path.exists():
        raise FileNotFoundError(f"Gold standard file not found: {gold_path}")

    with open(path) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Gold standard must be a JSON array of strings")

    return [str(item) for item in data]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_key_point_coverage(
    summary: str,
    key_points: list[str],
    threshold: float = _COVERAGE_THRESHOLD,
) -> float:
    """Compute the percentage of gold key points covered by the summary.

    A key point is "covered" if its embedding has cosine similarity
    >= *threshold* with the full summary embedding.
    """
    if not key_points:
        return 100.0

    # Embed summary and all key points together for efficiency.
    all_texts = [summary] + key_points
    embeddings = _embed_texts(all_texts)

    summary_emb = embeddings[0]
    point_embs = embeddings[1:]

    covered = 0
    for emb in point_embs:
        sim = _cosine_similarity(summary_emb, emb)
        if sim >= threshold:
            covered += 1

    return round(100.0 * covered / len(key_points), 2)


def _score_concision(
    summary: str,
    source_text: str,
) -> float:
    """Score concision as 100 * (1 - summary_len / source_len).

    Capped to [0, 100].  A summary longer than the source scores 0.
    """
    source_len = len(source_text.split())
    summary_len = len(summary.split())

    if source_len == 0:
        return 0.0

    ratio = summary_len / source_len
    score = 100.0 * (1.0 - ratio)
    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    summary: str,
    source_text: str,
    gold_path: str,
    *,
    threshold: float = _COVERAGE_THRESHOLD,
) -> dict:
    """Evaluate a summarisation output.

    Args:
        summary: The model's generated summary.
        source_text: The original source document that was summarised.
        gold_path: Path to a JSON file containing gold key-point strings.
        threshold: Cosine similarity threshold for coverage matching.

    Returns:
        Dict with key_point_coverage, factual_accuracy (None),
        hallucination_rate (None), and concision percentages.
    """
    key_points = load_gold_key_points(gold_path)

    key_point_coverage = _score_key_point_coverage(
        summary, key_points, threshold=threshold
    )
    concision = _score_concision(summary, source_text)

    return {
        "key_point_coverage": key_point_coverage,
        "factual_accuracy": None,       # placeholder — filled by LLM judge
        "hallucination_rate": None,      # placeholder — filled by LLM judge
        "concision": concision,
    }
