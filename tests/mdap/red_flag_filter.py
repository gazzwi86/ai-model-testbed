"""Pre-voting filter to discard obviously bad outputs.

Inspired by MAKER's red-flagging: remove responses with structural
indicators of failure before they enter the voting pool.
"""

import ast
import logging

from harness.utils import extract_code

logger = logging.getLogger(__name__)

DISALLOWED_PATTERNS = [
    "os.system",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
    "eval(",
    "exec(",
    "__import__(",
]


def red_flag_check(
    output: str,
    task_type: str = "code",
    max_lines: int | None = None,
    original_prompt: str | None = None,
) -> tuple[bool, str]:
    """Check an output for red flags.

    Returns (passed, reason). passed=True means output is acceptable.
    """
    if not output or not output.strip():
        return False, "Empty output"

    if task_type == "code":
        code = extract_code(output)

        # 1. Syntax check
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        # 2. Length check
        if max_lines and code.count("\n") > max_lines * 2:
            return False, (
                f"Output too long: {code.count(chr(10))} lines "
                f"vs {max_lines} expected max"
            )

        # 3. Disallowed patterns
        for pattern in DISALLOWED_PATTERNS:
            if pattern in code:
                return False, f"Disallowed pattern: {pattern}"

        # 4. Prompt echo detection
        if original_prompt and len(original_prompt) > 50:
            # If >60% of the prompt appears verbatim in the output, flag it
            prompt_words = set(original_prompt.lower().split())
            output_words = set(code.lower().split())
            overlap = len(prompt_words & output_words) / len(prompt_words)
            if overlap > 0.6:
                return False, f"Prompt echo detected (overlap: {overlap:.0%})"

    elif task_type == "text":
        # Text-specific checks
        if len(output.strip()) < 20:
            return False, "Text output too short (< 20 chars)"

        # Check for repetitive output (same sentence repeated)
        sentences = [s.strip() for s in output.split(".") if s.strip()]
        if len(sentences) > 3:
            unique = set(sentences)
            if len(unique) < len(sentences) * 0.5:
                return False, "Repetitive output detected"

    return True, "passed"


def filter_candidates(
    candidates: list[str],
    task_type: str = "code",
    max_lines: int | None = None,
    original_prompt: str | None = None,
) -> tuple[list[str], list[dict]]:
    """Filter a list of candidate outputs, returning accepted and discard log."""
    accepted = []
    discard_log = []

    for i, candidate in enumerate(candidates):
        passed, reason = red_flag_check(
            candidate, task_type, max_lines, original_prompt
        )
        if passed:
            accepted.append(candidate)
        else:
            discard_log.append({"index": i, "reason": reason})
            logger.debug("Filtered candidate %d: %s", i, reason)

    logger.info(
        "Filtered: %d accepted, %d discarded out of %d",
        len(accepted), len(discard_log), len(candidates),
    )
    return accepted, discard_log
