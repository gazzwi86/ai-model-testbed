"""Lint scoring evaluator.

Runs ruff and pylint on generated code and produces a combined quality score.

Returns:
    {"ruff_violations": int, "pylint_score": float, "quality_pct": float}
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_tool(name: str) -> str:
    """Find a CLI tool, preferring the venv's bin directory."""
    venv_bin = Path(sys.executable).parent / name
    if venv_bin.exists():
        return str(venv_bin)
    found = shutil.which(name)
    return found or name

# Each ruff violation costs this many points out of 100.
RUFF_VIOLATION_WEIGHT = 5.0


def _write_temp_file(code: str) -> Path:
    """Write code to a temporary .py file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="lint_"
    )
    tmp.write(code)
    tmp.close()
    return Path(tmp.name)


def _run_ruff(filepath: Path) -> int:
    """Run ruff check on *filepath* and return the number of violations."""
    try:
        result = subprocess.run(
            [_find_tool("ruff"), "check", "--output-format=json", str(filepath)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # ruff returns exit-code 1 when violations are found; that is fine.
        if result.stdout.strip():
            violations = json.loads(result.stdout)
            return len(violations)
        return 0
    except FileNotFoundError:
        logger.warning("ruff not found on PATH; skipping ruff scoring")
        return 0
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        logger.warning("ruff scoring failed: %s", exc)
        return 0


def _run_pylint(filepath: Path) -> float:
    """Run pylint on *filepath* and return the 0-10 score."""
    try:
        result = subprocess.run(
            [
                _find_tool("pylint"),
                "--output-format=json",
                "--disable=C0114,C0115,C0116",  # don't penalise missing module/class docstrings twice
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # pylint outputs a JSON array of messages. The score is on stderr
        # or can be extracted via --score=y. We parse stderr for the score line.
        for line in result.stderr.splitlines():
            if "rated at" in line:
                # Format: "Your code has been rated at 7.50/10 ..."
                score_str = line.split("rated at")[1].split("/")[0].strip()
                return float(score_str)

        # Fallback: if no messages, assume perfect score.
        if result.stdout.strip() in ("", "[]"):
            return 10.0

        return 5.0  # conservative default
    except FileNotFoundError:
        logger.warning("pylint not found on PATH; skipping pylint scoring")
        return 10.0
    except (subprocess.TimeoutExpired, ValueError) as exc:
        logger.warning("pylint scoring failed: %s", exc)
        return 5.0


def evaluate(code: str) -> dict:
    """Score *code* using ruff and pylint.

    Args:
        code: Python source code to lint.

    Returns:
        Dict with ruff_violations, pylint_score (0-10), and quality_pct (0-100).
    """
    filepath = _write_temp_file(code)
    try:
        ruff_violations = _run_ruff(filepath)
        pylint_score = _run_pylint(filepath)

        # Combine: start at 100, deduct per ruff violation, blend with pylint.
        ruff_quality = max(0.0, 100.0 - ruff_violations * RUFF_VIOLATION_WEIGHT)
        pylint_quality = pylint_score * 10.0  # scale 0-10 -> 0-100

        # Weighted average: 40% ruff, 60% pylint
        quality_pct = round(0.4 * ruff_quality + 0.6 * pylint_quality, 2)
        quality_pct = max(0.0, min(100.0, quality_pct))

        return {
            "ruff_violations": ruff_violations,
            "pylint_score": round(pylint_score, 2),
            "quality_pct": quality_pct,
        }
    finally:
        filepath.unlink(missing_ok=True)
