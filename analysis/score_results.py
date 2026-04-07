"""Aggregate raw results and compute sub-dimension percentage scores.

Reads JSON results from results/raw/, runs evaluators, writes scored
results to results/scored/.
"""

import json
import logging
from pathlib import Path

from harness.paths import SCORED_RESULTS_DIR
from .utils import load_raw_results

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


def score_result(result: dict) -> dict:
    """Score a single result using the appropriate evaluator."""
    category = result["category"]
    dimensions = DIMENSIONS.get(category, [])

    scores = {}
    try:
        if category == "code_gen":
            from tests.evaluators.code_correctness import evaluate
            scores = evaluate(result.get("response_text", ""))
        elif category == "code_review":
            from tests.evaluators.bug_detection import evaluate
            scores = evaluate(result.get("response_text", ""))
        elif category == "summarisation":
            from tests.evaluators.summary_coverage import evaluate
            scores = evaluate(
                result.get("response_text", ""),
                source_text="",
                gold_path="",
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


def score_all():
    """Score all raw results and save to scored directory."""
    SCORED_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = load_raw_results()

    logger.info("Scoring %d results", len(results))
    for result in results:
        scored = score_result(result)
        filename = Path(result.get("_source_file", "unknown")).stem + "_scored.json"
        out_path = SCORED_RESULTS_DIR / filename
        with open(out_path, "w") as f:
            json.dump(scored, f, indent=2)
        logger.info("Scored: %s", out_path.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    score_all()
