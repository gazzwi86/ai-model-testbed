"""Bug detection evaluator for code-review outputs.

Compares a model's code-review response against a bug manifest to
compute precision, recall, false-positive rate, and a placeholder
explanation-quality score (filled later by the LLM judge).

Returns:
    {
        "precision": float,
        "recall": float,
        "false_positive_rate": float,
        "explanation_quality": float | None,
    }

All percentages are in [0.0, 100.0].
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum fraction of a bug description's keywords that must appear in a
# response paragraph for it to count as a mention of that bug.
_KEYWORD_MATCH_THRESHOLD = 0.4

# Stop-words excluded from keyword matching.
_STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "of", "in", "to",
    "for", "with", "on", "at", "from", "by", "as", "or", "and", "but",
    "if", "not", "no", "so", "that", "this", "it", "its", "which",
}


# ---------------------------------------------------------------------------
# Bug-manifest loading
# ---------------------------------------------------------------------------

def load_bug_manifest(manifest_path: str) -> list[dict]:
    """Load and validate a bug manifest JSON file.

    Each entry must have at least: bug_id, description, severity, category.
    """
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Bug manifest not found: {manifest_path}")

    with open(path) as f:
        manifest = json.load(f)

    if not isinstance(manifest, list):
        raise ValueError("Bug manifest must be a JSON array")

    for entry in manifest:
        for key in ("bug_id", "description"):
            if key not in entry:
                raise ValueError(f"Bug manifest entry missing required key: {key}")

    return manifest


# ---------------------------------------------------------------------------
# Response parsing — fuzzy keyword matching
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful lowercase keywords from a text snippet."""
    words = re.findall(r"[a-z_][a-z0-9_]*", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _paragraphs(response: str) -> list[str]:
    """Split the model response into rough paragraphs / bullet points."""
    # Split on double newlines or numbered/bulleted list items.
    chunks = re.split(r"\n{2,}|\n(?=\s*[-*\d]+[.)\]]?\s)", response)
    return [c.strip() for c in chunks if c.strip()]


def _bug_mentioned(
    bug: dict,
    paragraphs: list[str],
    paragraph_keyword_sets: list[set[str]],
) -> bool:
    """Return True if a bug's description keywords appear in any paragraph."""
    bug_keywords = _extract_keywords(bug["description"])
    if not bug_keywords:
        return False

    for kw_set in paragraph_keyword_sets:
        overlap = bug_keywords & kw_set
        if len(overlap) / len(bug_keywords) >= _KEYWORD_MATCH_THRESHOLD:
            return True
    return False


def _count_reported_bugs(
    paragraphs: list[str],
) -> int:
    """Estimate the total number of distinct bugs the model reported.

    Heuristic: count paragraphs that look like bug reports (contain words
    like 'bug', 'error', 'issue', 'problem', 'flaw', 'vulnerability',
    'missing', 'incorrect', 'wrong', or reference line numbers).
    """
    bug_indicators = re.compile(
        r"\b(bug|error|issue|problem|flaw|vulnerability|missing|incorrect|"
        r"wrong|off-by-one|leak|overflow|uninitialized|unclosed|unused|"
        r"line\s*\d+)\b",
        re.IGNORECASE,
    )
    return sum(1 for p in paragraphs if bug_indicators.search(p))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    response: str,
    manifest_path: str,
) -> dict:
    """Evaluate a code-review response against a bug manifest.

    Args:
        response: The model's code-review output.
        manifest_path: Path to the bug manifest JSON file.

    Returns:
        Dict with precision, recall, false_positive_rate, and
        explanation_quality (placeholder None).
    """
    manifest = load_bug_manifest(manifest_path)
    paragraphs = _paragraphs(response)
    paragraph_kw_sets = [_extract_keywords(p) for p in paragraphs]

    # Which planted bugs did the model find?
    found_bugs: list[dict] = []
    for bug in manifest:
        if _bug_mentioned(bug, paragraphs, paragraph_kw_sets):
            found_bugs.append(bug)

    total_planted = len(manifest)
    correct_found = len(found_bugs)
    total_reported = _count_reported_bugs(paragraphs)

    # Guard against division by zero
    if total_reported == 0:
        precision = 0.0
        false_positive_count = 0
    else:
        precision = round(100.0 * correct_found / total_reported, 2)
        false_positive_count = max(0, total_reported - correct_found)

    if total_planted == 0:
        recall = 100.0
    else:
        recall = round(100.0 * correct_found / total_planted, 2)

    if total_reported == 0:
        false_positive_rate = 0.0
    else:
        false_positive_rate = round(
            100.0 * false_positive_count / total_reported, 2
        )

    return {
        "precision": precision,
        "recall": recall,
        "false_positive_rate": false_positive_rate,
        "explanation_quality": None,  # placeholder — filled by LLM judge
    }
