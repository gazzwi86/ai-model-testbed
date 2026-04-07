"""Aggregate raw results and compute sub-dimension percentage scores.

Reads JSON results from results/raw/, runs evaluators, writes scored
results to results/scored/.
"""

import json
import logging
from pathlib import Path

from harness.paths import SCORED_RESULTS_DIR, RAW_RESULTS_DIR, FIXTURES_DIR

logger = logging.getLogger(__name__)

DIMENSIONS = {
    "code_gen": ["correctness", "quality", "completeness", "style"],
    "code_review": ["precision", "recall", "false_positive_rate", "explanation_quality"],
    "summarisation": ["key_point_coverage", "factual_accuracy", "hallucination_rate", "concision"],
    "writing": ["clarity", "accuracy", "engagement", "originality", "register"],
    "data_analysis": ["output_correctness", "edge_case_handling", "narrative_quality"],
    "reasoning": ["factual_accuracy", "nuance", "actionability", "hallucination_rate"],
    "tool_use": ["format_compliance", "task_completion", "attempt_efficiency"],
}

# Bug manifest paths for code review tiers
BUG_MANIFESTS = {
    "simple": FIXTURES_DIR / "code_review" / "simple_bugs.json",
    "medium": FIXTURES_DIR / "code_review" / "medium_bugs.json",
    "hard": FIXTURES_DIR / "code_review" / "hard_bugs.json",
}

# Summarisation gold standard paths
GOLD_STANDARDS = {
    "simple": FIXTURES_DIR / "summarisation" / "gold" / "simple_gold.json",
    "medium": FIXTURES_DIR / "summarisation" / "gold" / "medium_gold.json",
    "hard": FIXTURES_DIR / "summarisation" / "gold" / "hard_gold.json",
}

# Summarisation source documents
SOURCE_DOCS = {
    "simple": FIXTURES_DIR / "summarisation" / "simple_transcript.md",
    "medium": FIXTURES_DIR / "summarisation" / "medium_architecture.md",
    "hard": FIXTURES_DIR / "summarisation" / "hard_rfp.md",
}


def score_result(result: dict) -> dict:
    """Score a single result using the appropriate evaluator."""
    category = result["category"]
    tier = result.get("tier", "simple")
    dimensions = DIMENSIONS.get(category, [])

    scores = {}
    try:
        if category == "code_gen":
            from tests.evaluators.code_correctness import evaluate
            scores = evaluate(result.get("response_text", ""))

        elif category == "code_review":
            from tests.evaluators.bug_detection import evaluate
            manifest_path = str(BUG_MANIFESTS.get(tier, ""))
            scores = evaluate(result.get("response_text", ""), manifest_path)

        elif category == "summarisation":
            from tests.evaluators.summary_coverage import evaluate
            gold_path = str(GOLD_STANDARDS.get(tier, ""))
            source_path = SOURCE_DOCS.get(tier)
            source_text = source_path.read_text() if source_path and source_path.exists() else ""
            scores = evaluate(
                result.get("response_text", ""),
                source_text=source_text,
                gold_path=gold_path,
            )

        elif category == "tool_use":
            from tests.evaluators.tool_format import evaluate
            scores = evaluate(result.get("response_text", ""))

        else:
            from tests.evaluators.llm_judge import evaluate
            scores = evaluate(
                result.get("response_text", ""),
                category,
            )
    except Exception as e:
        logger.error("Scoring failed for %s/%s: %s", category, result.get("test_name"), e)
        scores = {dim: None for dim in dimensions}

    result["scores"] = scores
    return result


def _result_filename(result: dict) -> str:
    """Generate a unique filename for a scored result."""
    parts = [
        result.get("category", "unknown"),
        result.get("tier", "unknown"),
        result.get("model_id", "unknown").replace(":", "_"),
        f"run{result.get('run_idx', 0)}",
    ]
    return "_".join(parts) + "_scored.json"


def score_all():
    """Score all raw results and save to scored directory."""
    SCORED_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for path in sorted(RAW_RESULTS_DIR.glob("*.json")):
        with open(path) as f:
            result = json.load(f)
        result["_source_file"] = str(path)
        results.append(result)

    logger.info("Scoring %d results", len(results))
    for result in results:
        scored = score_result(result)
        filename = _result_filename(scored)
        out_path = SCORED_RESULTS_DIR / filename
        with open(out_path, "w") as f:
            json.dump(scored, f, indent=2)
        logger.info("Scored: %s", out_path.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    score_all()
