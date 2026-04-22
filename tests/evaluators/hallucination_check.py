"""Hallucination checker.

Splits model output into sentence-level claims and checks each against
the source document using embedding similarity.  Claims with low
similarity to all source chunks are flagged as potential hallucinations.

Returns:
    {
        "hallucination_count": int,
        "hallucination_rate": float,   # percentage 0-100
        "flagged_claims": list[str],
    }
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# A claim is flagged if its max similarity to any source chunk is below this.
_SIMILARITY_THRESHOLD = 0.3

# Source document is split into chunks of roughly this many words.
_CHUNK_SIZE_WORDS = 100
_CHUNK_OVERLAP_WORDS = 20


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------

def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using a simple regex heuristic."""
    # Split on sentence-ending punctuation followed by whitespace.
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    # Filter out very short fragments that are unlikely to be claims.
    return [s.strip() for s in raw if len(s.split()) >= 4]


def _chunk_source(text: str, chunk_size: int = _CHUNK_SIZE_WORDS,
                  overlap: int = _CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split source document into overlapping word-level chunks."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


from .embedding_utils import cosine_similarity as _cosine_similarity, embed_texts as _embed_texts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    model_output: str,
    source_document: str,
    *,
    similarity_threshold: float = _SIMILARITY_THRESHOLD,
) -> dict:
    """Check for hallucinations in *model_output* vs *source_document*.

    Args:
        model_output: The model's generated text.
        source_document: The original source/reference document.
        similarity_threshold: Claims with max chunk similarity below this
            are flagged as potential hallucinations.

    Returns:
        Dict with hallucination_count, hallucination_rate (percentage),
        and flagged_claims (list of flagged sentence strings).
    """
    claims = _split_into_sentences(model_output)
    if not claims:
        return {
            "hallucination_count": 0,
            "hallucination_rate": 0.0,
            "flagged_claims": [],
        }

    chunks = _chunk_source(source_document)
    if not chunks:
        # No source to compare against — flag everything.
        return {
            "hallucination_count": len(claims),
            "hallucination_rate": 100.0,
            "flagged_claims": claims,
        }

    # Embed all claims and chunks together.
    all_texts = claims + chunks
    embeddings = _embed_texts(all_texts)

    claim_embs = embeddings[: len(claims)]
    chunk_embs = embeddings[len(claims):]

    flagged: list[str] = []

    for i, claim in enumerate(claims):
        max_sim = max(
            _cosine_similarity(claim_embs[i], chunk_embs[j])
            for j in range(len(chunks))
        )
        if max_sim < similarity_threshold:
            flagged.append(claim)

    hallucination_rate = round(100.0 * len(flagged) / len(claims), 2)

    return {
        "hallucination_count": len(flagged),
        "hallucination_rate": hallucination_rate,
        "flagged_claims": flagged,
    }
