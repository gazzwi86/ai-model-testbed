"""Tool-use format evaluator.

Validates tool-call JSON in model output against a provided schema,
scores format compliance, task completion, and attempt efficiency.

Returns:
    {
        "format_compliance": float,
        "task_completion": float,
        "attempt_efficiency": float,
    }

All percentages are in [0.0, 100.0].
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON extraction from model output
# ---------------------------------------------------------------------------

def _extract_json_blocks(response: str) -> list[str]:
    """Extract JSON objects/arrays from a model response.

    Handles both fenced code blocks (```json ... ```) and bare JSON
    objects found in the text.
    """
    blocks: list[str] = []

    # 1. Fenced code blocks labelled json
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
    blocks.extend(fenced)

    # 2. Bare JSON objects/arrays (greedy brace/bracket matching)
    for match in re.finditer(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", response):
        candidate = match.group(1)
        if candidate not in blocks:
            blocks.append(candidate)

    return blocks


def _parse_tool_calls(response: str) -> list[dict]:
    """Parse tool-call dicts from model response.

    Returns a list of dicts, each expected to represent a single tool call.
    """
    raw_blocks = _extract_json_blocks(response)
    calls: list[dict] = []

    for block in raw_blocks:
        try:
            parsed = json.loads(block.strip())
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            calls.append(parsed)
        elif isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    calls.append(item)

    return calls


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _validate_against_schema(call: dict, schema: dict) -> bool:
    """Validate a single tool call dict against a JSON schema.

    Uses jsonschema if available; falls back to basic structural checks.
    """
    try:
        import jsonschema
        jsonschema.validate(instance=call, schema=schema)
        return True
    except ImportError:
        # Fallback: check required properties exist.
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        for key in required:
            if key not in call:
                return False
        # Check top-level property types loosely
        for key, prop_schema in properties.items():
            if key in call and "type" in prop_schema:
                expected_type = prop_schema["type"]
                value = call[key]
                type_map = {
                    "string": str,
                    "integer": int,
                    "number": (int, float),
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                if expected_type in type_map:
                    if not isinstance(value, type_map[expected_type]):
                        return False
        return True
    except jsonschema.ValidationError:
        return False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_format_compliance(
    calls: list[dict],
    schema: dict | None,
) -> float:
    """Percentage of parsed tool calls that validate against schema."""
    if not calls:
        return 0.0
    if schema is None:
        # No schema to validate against; count any parseable JSON as valid.
        return 100.0

    valid = sum(1 for c in calls if _validate_against_schema(c, schema))
    return round(100.0 * valid / len(calls), 2)


def _score_task_completion(
    calls: list[dict],
    required_steps: list[str] | None,
) -> float:
    """Percentage of required steps that were completed.

    Each required step is a tool/function name that must appear as
    the value of a "name", "function", or "tool" key in at least one call.
    """
    if not required_steps:
        return 100.0

    call_names: set[str] = set()
    for call in calls:
        for key in ("name", "function", "tool", "action"):
            if key in call and isinstance(call[key], str):
                call_names.add(call[key].lower())

    completed = sum(
        1 for step in required_steps if step.lower() in call_names
    )
    return round(100.0 * completed / len(required_steps), 2)


def _score_attempt_efficiency(
    calls: list[dict],
    expected_call_count: int | None,
) -> float:
    """Efficiency score: 100 / (attempts / expected), capped at 100.

    If the model used fewer or equal attempts than expected, score is 100.
    Extra attempts reduce the score.
    """
    if expected_call_count is None or expected_call_count <= 0:
        return 100.0

    actual = len(calls)
    if actual == 0:
        return 0.0
    if actual <= expected_call_count:
        return 100.0

    return round(min(100.0, 100.0 * expected_call_count / actual), 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    response: str,
    *,
    tool_schema: dict | None = None,
    required_steps: list[str] | None = None,
    expected_call_count: int | None = None,
) -> dict:
    """Evaluate a tool-use model response.

    Args:
        response: The full model output containing tool-call JSON.
        tool_schema: JSON Schema dict to validate each tool call against.
        required_steps: List of tool/function names that must be called.
        expected_call_count: Optimal number of tool calls for efficiency scoring.

    Returns:
        Dict with format_compliance, task_completion, and attempt_efficiency
        as percentages.
    """
    calls = _parse_tool_calls(response)

    format_compliance = _score_format_compliance(calls, tool_schema)
    task_completion = _score_task_completion(calls, required_steps)
    attempt_efficiency = _score_attempt_efficiency(calls, expected_call_count)

    return {
        "format_compliance": format_compliance,
        "task_completion": task_completion,
        "attempt_efficiency": attempt_efficiency,
    }
