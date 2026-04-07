"""Voting strategies for selecting the best candidate output.

Three strategies:
1. functional_vote: For code — run test assertions, score by pass rate
2. embedding_vote: For text — centroid selection via sentence-transformers
3. pairwise_rank_vote: For text — LLM-based pairwise comparison (LLM-Blender inspired)
"""

import logging
import subprocess
import tempfile
import textwrap
from pathlib import Path

import numpy as np

from harness.utils import extract_code
from tests.evaluators.embedding_utils import (
    cosine_similarity,
    embed_texts,
    get_model as get_embedding_model,
)

logger = logging.getLogger(__name__)

# Module-level Anthropic client cache for pairwise voting
_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _run_tests(code: str, test_assertions: list[str]) -> list[bool]:
    """Execute code + all test assertions in a single subprocess."""
    if not test_assertions:
        return []

    # Batch all assertions into one script for efficiency
    test_lines = []
    for i, assertion in enumerate(test_assertions):
        test_lines.append(f"try:")
        test_lines.append(f"    {assertion}")
        test_lines.append(f"    print('PASS:{i}')")
        test_lines.append(f"except Exception:")
        test_lines.append(f"    print('FAIL:{i}')")

    test_script = code + "\n\n" + "\n".join(test_lines)

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "test_candidate.py"
        script_path.write_text(test_script)
        try:
            result = subprocess.run(
                ["python", str(script_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            results = []
            for i in range(len(test_assertions)):
                results.append(f"PASS:{i}" in output)
            return results
        except (subprocess.TimeoutExpired, Exception):
            return [False] * len(test_assertions)


def functional_vote(
    candidates: list[str],
    test_assertions: list[str],
) -> tuple[str | None, dict]:
    """Vote by running test assertions. Return candidate with most passes.

    Returns (winning_candidate, vote_details).
    """
    if not candidates:
        return None, {"error": "no candidates"}

    scores = []
    for i, candidate in enumerate(candidates):
        code = extract_code(candidate)
        passed = _run_tests(code, test_assertions)
        pass_count = sum(passed)
        scores.append({
            "index": i,
            "passed": passed,
            "pass_count": pass_count,
            "pass_rate": pass_count / len(test_assertions) if test_assertions else 0,
        })

    scores.sort(key=lambda s: (-s["pass_count"], len(candidates[s["index"]])))

    winner_idx = scores[0]["index"]
    details = {
        "method": "functional",
        "scores": scores,
        "winner_index": winner_idx,
        "winner_pass_rate": scores[0]["pass_rate"],
    }

    logger.info(
        "Functional vote: winner=%d (%.0f%% pass rate)",
        winner_idx, scores[0]["pass_rate"] * 100,
    )
    return candidates[winner_idx], details


def embedding_vote(
    candidates: list[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> tuple[str | None, dict]:
    """Vote by selecting the candidate closest to the centroid embedding."""
    if not candidates:
        return None, {"error": "no candidates"}
    if len(candidates) == 1:
        return candidates[0], {"method": "embedding", "winner_index": 0, "note": "single candidate"}

    embeddings = embed_texts(candidates, model_name)

    centroid = np.mean(embeddings, axis=0)
    similarities = [
        cosine_similarity(emb, centroid) for emb in embeddings
    ]

    winner_idx = int(np.argmax(similarities))
    details = {
        "method": "embedding",
        "similarities": similarities,
        "winner_index": winner_idx,
        "winner_similarity": similarities[winner_idx],
    }

    logger.info(
        "Embedding vote: winner=%d (similarity=%.4f)",
        winner_idx, similarities[winner_idx],
    )
    return candidates[winner_idx], details


def pairwise_rank_vote(
    candidates: list[str],
    task_description: str,
    judge_model: str = "claude-sonnet-4-6",
) -> tuple[str | None, dict]:
    """Vote via pairwise comparison using an LLM judge.

    Inspired by LLM-Blender's PairRanker. Selects the Condorcet winner.
    """
    if not candidates:
        return None, {"error": "no candidates"}
    if len(candidates) == 1:
        return candidates[0], {"method": "pairwise_rank", "winner_index": 0}

    client = _get_anthropic_client()
    wins = [0] * len(candidates)
    comparisons = []

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            prompt = textwrap.dedent(f"""\
                Compare these two responses to the following task.
                Which is better? Reply with ONLY "A" or "B".

                ## Task
                {task_description}

                ## Response A
                {candidates[i]}

                ## Response B
                {candidates[j]}

                Which response is better? Reply with ONLY the letter "A" or "B".
            """)

            try:
                response = client.messages.create(
                    model=judge_model,
                    max_tokens=10,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                answer = response.content[0].text.strip().upper()
                if "A" in answer:
                    wins[i] += 1
                    comparisons.append({"a": i, "b": j, "winner": "A"})
                else:
                    wins[j] += 1
                    comparisons.append({"a": i, "b": j, "winner": "B"})
            except Exception as e:
                logger.warning("Pairwise comparison failed (%d vs %d): %s", i, j, e)
                comparisons.append({"a": i, "b": j, "winner": "error"})

    winner_idx = int(np.argmax(wins))
    details = {
        "method": "pairwise_rank",
        "wins": wins,
        "comparisons": comparisons,
        "winner_index": winner_idx,
        "winner_wins": wins[winner_idx],
    }

    logger.info(
        "Pairwise rank vote: winner=%d (%d wins)",
        winner_idx, wins[winner_idx],
    )
    return candidates[winner_idx], details


def hybrid_vote(
    candidates: list[str],
    task_type: str,
    test_assertions: list[str] | None = None,
    task_description: str = "",
    embedding_model: str = "all-MiniLM-L6-v2",
    judge_model: str = "claude-sonnet-4-6",
) -> tuple[str | None, dict]:
    """Select voting strategy based on task type.

    For code: try functional vote first, fall back to embedding.
    For text: run both embedding and pairwise rank, compare.
    """
    if task_type == "code" and test_assertions:
        winner, details = functional_vote(candidates, test_assertions)
        if winner and details.get("winner_pass_rate", 0) > 0:
            return winner, details
        logger.info("Functional vote found no passing candidates, falling back to embedding")
        return embedding_vote(candidates, embedding_model)

    elif task_type == "text":
        emb_winner, emb_details = embedding_vote(candidates, embedding_model)
        pair_winner, pair_details = pairwise_rank_vote(
            candidates, task_description, judge_model
        )

        emb_idx = emb_details.get("winner_index")
        pair_idx = pair_details.get("winner_index")
        details = {
            "method": "hybrid_text",
            "embedding": emb_details,
            "pairwise_rank": pair_details,
            "agreement": emb_idx == pair_idx if emb_idx is not None and pair_idx is not None else None,
        }
        return pair_winner if pair_winner is not None else emb_winner, details

    else:
        return embedding_vote(candidates, embedding_model)
