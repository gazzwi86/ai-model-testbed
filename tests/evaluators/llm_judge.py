"""LLM judge evaluator using Claude as a structured scorer.

Uses claude-agent-sdk (Claude Code CLI) for authentication, supporting
OAuth tokens from Claude subscriptions.

Returns:
    Dict of axis_name -> float (percentage 0-100), plus "justifications"
    mapping axis_name -> one-line string.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import claude_agent_sdk

logger = logging.getLogger(__name__)

_JUDGE_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Evaluation axes per category
# ---------------------------------------------------------------------------

AXES: dict[str, list[str]] = {
    "code_review": ["explanation_quality"],
    "summarisation": ["factual_accuracy", "hallucination_rate"],
    "writing": ["clarity", "accuracy", "engagement", "originality", "register"],
    "reasoning": [
        "factual_accuracy", "nuance", "actionability", "hallucination_rate",
    ],
    "data_analysis": ["narrative_quality"],
}


# ---------------------------------------------------------------------------
# Rubric prompt
# ---------------------------------------------------------------------------

def _build_judge_prompt(
    model_output: str,
    category: str,
    axes: list[str],
    gold_standard: str | None = None,
) -> str:
    axes_list = "\n".join(f"  - {axis}" for axis in axes)

    gold_section = ""
    if gold_standard:
        gold_section = (
            "\n<gold_standard>\n"
            f"{gold_standard}\n"
            "</gold_standard>\n"
        )

    return f"""\
You are an expert evaluator for a language-model benchmark. Your task is to
score the following model output on specific quality axes.

<category>{category}</category>
{gold_section}
<model_output>
{model_output}
</model_output>

Score the model output on EACH of the following axes using a 1-5 scale:

{axes_list}

Scoring guide:
  1 = Very poor — fundamentally wrong, missing, or incoherent
  2 = Poor — major issues, partially addresses the task
  3 = Adequate — acceptable quality with some notable gaps
  4 = Good — solid quality with minor issues
  5 = Excellent — exceptional quality, no meaningful issues

For each axis, provide:
  1. A numeric score from 1 to 5 (integers only).
  2. A one-line justification explaining your score.

Return your evaluation as a JSON object with exactly this structure:
{{
  "scores": {{
    "<axis_name>": <score_int>,
    ...
  }},
  "justifications": {{
    "<axis_name>": "<one line justification>",
    ...
  }}
}}

Return ONLY the JSON object, no other text.
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_judge_response(response_text: str, axes: list[str]) -> dict:
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not json_match:
        logger.warning("Could not extract JSON from judge response")
        return {axis: None for axis in axes}

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse judge JSON: %s", exc)
        return {axis: None for axis in axes}

    scores_raw = data.get("scores", {})
    justifications = data.get("justifications", {})

    result: dict = {}
    for axis in axes:
        raw_score = scores_raw.get(axis)
        if raw_score is not None:
            try:
                score_int = int(raw_score)
                score_int = max(1, min(5, score_int))
                result[axis] = round(score_int / 5 * 100, 2)
            except (ValueError, TypeError):
                result[axis] = None
        else:
            result[axis] = None

    result["justifications"] = {
        axis: justifications.get(axis, "") for axis in axes
    }

    return result


# ---------------------------------------------------------------------------
# Internal async query
# ---------------------------------------------------------------------------

async def _query_judge(prompt: str, judge_model: str) -> str:
    """Call Claude via agent SDK and return the response text."""
    options = claude_agent_sdk.ClaudeAgentOptions(
        model=judge_model,
        max_turns=1,
        permission_mode="bypassPermissions",
    )

    result_text = ""
    async for event in claude_agent_sdk.query(prompt=prompt, options=options):
        if isinstance(event, claude_agent_sdk.AssistantMessage):
            for block in event.content:
                if isinstance(block, claude_agent_sdk.TextBlock):
                    result_text += block.text
        elif isinstance(event, claude_agent_sdk.ResultMessage):
            if event.result and not result_text:
                result_text = event.result
    return result_text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    model_output: str,
    category: str,
    *,
    gold_standard: str | None = None,
    axes_override: list[str] | None = None,
    judge_model: str = _JUDGE_MODEL,
) -> dict:
    """Score *model_output* using Claude as a structured judge."""
    axes = axes_override or AXES.get(category)
    if not axes:
        raise ValueError(
            f"No evaluation axes defined for category '{category}'. "
            f"Provide axes_override or use one of: {list(AXES.keys())}"
        )

    prompt = _build_judge_prompt(model_output, category, axes, gold_standard)

    try:
        # Run async query from sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context — use nest_asyncio or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                response_text = pool.submit(
                    asyncio.run, _query_judge(prompt, judge_model)
                ).result()
        else:
            response_text = asyncio.run(_query_judge(prompt, judge_model))

    except Exception as exc:
        logger.error("LLM judge call failed: %s", exc)
        result = {axis: None for axis in axes}
        result["justifications"] = {axis: f"Judge call failed: {exc}" for axis in axes}
        return result

    return _parse_judge_response(response_text, axes)
