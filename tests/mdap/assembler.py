"""Assemble voted subtask outputs into a final module and run integration tests."""

import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from harness.utils import extract_code

logger = logging.getLogger(__name__)


@dataclass
class AssemblyResult:
    assembled_code: str
    subtask_outputs: dict[str, str]
    integration_test_passed: bool
    integration_test_output: str
    individual_test_results: dict[str, bool] = field(default_factory=dict)


def assemble_code(
    subtask_outputs: dict[str, str],
    subtask_order: list[str],
) -> str:
    """Concatenate subtask code outputs in dependency order."""
    parts = []
    seen_imports = set()

    for subtask_id in subtask_order:
        if subtask_id not in subtask_outputs:
            logger.warning("Missing output for subtask %s", subtask_id)
            continue

        code = extract_code(subtask_outputs[subtask_id])

        # Extract and deduplicate imports
        lines = code.split("\n")
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                if stripped not in seen_imports:
                    seen_imports.add(stripped)
                    code_lines.append(line)
            else:
                code_lines.append(line)

        parts.append(f"# --- {subtask_id} ---")
        parts.append("\n".join(code_lines))
        parts.append("")

    # Put all imports at the top
    imports = sorted(seen_imports)
    body_parts = []
    for part in parts:
        body_lines = []
        for line in part.split("\n"):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                body_lines.append(line)
        body_parts.append("\n".join(body_lines))

    return "\n".join(imports) + "\n\n" + "\n".join(body_parts)


def assemble_text(
    subtask_outputs: dict[str, str],
    subtask_order: list[str],
) -> str:
    """Concatenate text outputs in dependency order with section breaks."""
    parts = []
    for subtask_id in subtask_order:
        if subtask_id not in subtask_outputs:
            continue
        parts.append(subtask_outputs[subtask_id].strip())
    return "\n\n---\n\n".join(parts)


def run_integration_tests(
    assembled_code: str,
    test_file: str | Path,
) -> tuple[bool, str]:
    """Run an integration test file against the assembled code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write assembled code
        code_path = Path(tmpdir) / "module.py"
        code_path.write_text(assembled_code)

        # Copy test file
        test_content = Path(test_file).read_text()
        test_path = Path(tmpdir) / "test_module.py"
        test_path.write_text(test_content)

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tmpdir,
                env={"PYTHONPATH": tmpdir},
            )
            passed = result.returncode == 0
            output = result.stdout + "\n" + result.stderr
        except subprocess.TimeoutExpired:
            passed = False
            output = "Integration tests timed out (30s)"
        except Exception as e:
            passed = False
            output = f"Integration test error: {e}"

    return passed, output


def assemble_and_test(
    subtask_outputs: dict[str, str],
    subtask_order: list[str],
    task_type: str,
    integration_test_file: str | Path | None = None,
) -> AssemblyResult:
    """Full assembly pipeline: concatenate outputs and run integration tests."""
    if task_type == "code":
        assembled = assemble_code(subtask_outputs, subtask_order)
    else:
        assembled = assemble_text(subtask_outputs, subtask_order)

    if integration_test_file and task_type == "code":
        passed, output = run_integration_tests(assembled, integration_test_file)
    else:
        passed = True
        output = "No integration tests configured"

    return AssemblyResult(
        assembled_code=assembled,
        subtask_outputs=subtask_outputs,
        integration_test_passed=passed,
        integration_test_output=output,
    )
