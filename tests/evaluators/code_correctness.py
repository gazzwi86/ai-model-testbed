"""Code correctness evaluator.

Extracts code from model responses, runs test assertions, checks
completeness against a checklist, scores style, and delegates lint
quality to lint_scorer.

Returns:
    {"correctness": float, "completeness": float, "quality": float, "style": float}

All values are percentages in [0.0, 100.0].
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from harness.utils import extract_code
from . import lint_scorer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Correctness — run pytest assertions
# ---------------------------------------------------------------------------

def _score_correctness(code: str, test_file: str | None) -> float:
    """Run the prompt's test file against the extracted code.

    The test file is expected to import from a module named ``solution``.
    We write the extracted code as ``solution.py`` in a temp directory,
    copy the test file alongside it, and run pytest.

    Returns a percentage of assertions passed.
    """
    if not test_file or not Path(test_file).exists():
        logger.info("No test_file provided or file missing; skipping correctness")
        return 0.0

    tmpdir = Path(tempfile.mkdtemp(prefix="code_eval_"))
    solution_path = tmpdir / "solution.py"
    test_path = tmpdir / "test_solution.py"

    try:
        solution_path.write_text(code)

        # Read original test file and make sure it imports from solution
        test_source = Path(test_file).read_text()
        test_path.write_text(test_source)

        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_path),
                "-v",
                "--tb=short",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmpdir),
        )

        output = result.stdout + result.stderr
        passed = len(re.findall(r" PASSED", output))
        failed = len(re.findall(r" FAILED", output))
        errors = len(re.findall(r" ERROR", output))
        total = passed + failed + errors

        if total == 0:
            return 0.0
        return round(100.0 * passed / total, 2)

    except subprocess.TimeoutExpired:
        logger.warning("Test execution timed out")
        return 0.0
    except Exception as exc:
        logger.warning("Test execution failed: %s", exc)
        return 0.0
    finally:
        # Clean up temp files
        for p in tmpdir.iterdir():
            p.unlink(missing_ok=True)
        tmpdir.rmdir()


# ---------------------------------------------------------------------------
# Completeness — checklist items present in code
# ---------------------------------------------------------------------------

def _score_completeness(code: str, checklist: list[str] | None) -> float:
    """Check what fraction of checklist items appear in the code.

    Each checklist item is a short phrase or keyword. We do a simple
    case-insensitive substring match.

    Returns a percentage of items found.
    """
    if not checklist:
        return 100.0  # no checklist means nothing to miss

    found = 0
    code_lower = code.lower()
    for item in checklist:
        if item.lower() in code_lower:
            found += 1
    return round(100.0 * found / len(checklist), 2)


# ---------------------------------------------------------------------------
# Style — structural quality checks via AST inspection
# ---------------------------------------------------------------------------

def _score_style(code: str) -> float:
    """Score style based on presence of type hints, docstrings,
    naming conventions, and context-manager usage.

    Four sub-checks, each worth 25 points:
    1. Type hints present on at least one function.
    2. Docstring present on at least one function.
    3. Follows snake_case naming for functions and variables.
    4. Uses context managers (``with`` statements) where files are opened.
    """
    checks_passed = 0
    total_checks = 4

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0.0

    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    # 1. Type hints
    has_type_hints = any(
        fn.returns is not None or any(
            arg.annotation is not None
            for arg in fn.args.args
        )
        for fn in functions
    )
    if has_type_hints:
        checks_passed += 1

    # 2. Docstrings
    has_docstring = any(
        (fn.body
         and isinstance(fn.body[0], ast.Expr)
         and isinstance(fn.body[0].value, ast.Constant))
        for fn in functions
    )
    if has_docstring:
        checks_passed += 1

    # 3. Naming conventions (snake_case for functions)
    snake_case_re = re.compile(r"^[a-z_][a-z0-9_]*$")
    if functions:
        all_snake = all(snake_case_re.match(fn.name) for fn in functions)
        if all_snake:
            checks_passed += 1
    else:
        checks_passed += 1  # no functions to check

    # 4. Context managers — if open() is called, 'with' should be used
    has_open_call = "open(" in code
    has_with_stmt = any(
        isinstance(node, ast.With) for node in ast.walk(tree)
    )
    if not has_open_call or has_with_stmt:
        checks_passed += 1

    return round(100.0 * checks_passed / total_checks, 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    response: str,
    *,
    test_file: str | None = None,
    checklist: list[str] | None = None,
) -> dict:
    """Evaluate a code-generation model response.

    Args:
        response: The full model output (may contain markdown).
        test_file: Path to a pytest file that tests the generated code.
        checklist: List of keywords/phrases the code should contain.

    Returns:
        Dict with correctness, completeness, quality, and style percentages.
    """
    code = extract_code(response)

    correctness = _score_correctness(code, test_file)
    completeness = _score_completeness(code, checklist)
    lint_result = lint_scorer.evaluate(code)
    quality = lint_result["quality_pct"]
    style = _score_style(code)

    return {
        "correctness": correctness,
        "completeness": completeness,
        "quality": quality,
        "style": style,
    }
