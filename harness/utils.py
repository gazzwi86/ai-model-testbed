"""Shared utilities used across harness, evaluators, and MDAP modules."""

import re

_CODE_BLOCK_RE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL
)
_GENERIC_BLOCK_RE = re.compile(
    r"```\s*\n(.*?)```", re.DOTALL
)


def extract_code(response: str) -> str:
    """Extract Python code from a model response.

    Tries python-specific fenced blocks first, then generic fenced blocks,
    then falls back to the entire response.
    """
    matches = _CODE_BLOCK_RE.findall(response)
    if matches:
        return "\n\n".join(matches)

    matches = _GENERIC_BLOCK_RE.findall(response)
    if matches:
        return "\n\n".join(matches)

    return response.strip()
