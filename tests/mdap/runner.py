"""Full MDAP orchestrator.

Decompose (Opus) → Execute (local models × k) → Filter → Vote → Assemble

Supports:
- Same-model voting: k inferences of one model, vote among them
- Cross-model ensemble: 1 inference per model, vote across all
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import yaml

from harness.config_loader import load_config, Config
from harness.ollama_client import OllamaClient
from harness.model_lifecycle import ensure_capacity
from .decomposer import Decomposer, SubTask
from .microagent import MicroagentRunner
from .red_flag_filter import filter_candidates
from .voter import hybrid_vote
from .assembler import assemble_and_test
from .cost_tracker import CostTracker

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "raw"


@dataclass
class MDAPResult:
    task_name: str
    approach: str  # "same_model" or "cross_model"
    model_id: str | None  # for same_model
    k: int
    task_type: str
    decomposition_subtask_count: int
    per_subtask_results: dict
    assembled_output: str
    integration_test_passed: bool
    integration_test_output: str
    cost_summary: dict
    voting_details: dict
    timestamp: str


async def run_mdap_same_model(
    task_description: str,
    task_name: str,
    task_type: str,
    model_id: str,
    config: Config,
    k: int | None = None,
    integration_test_file: str | None = None,
    pre_decomposed: list[SubTask] | None = None,
) -> MDAPResult:
    """Run full MDAP pipeline with same-model voting."""
    k = k or config.test_params.mdap_k
    cost_tracker = CostTracker(config)

    # Step 1: Decompose
    if pre_decomposed:
        subtasks = pre_decomposed
        task_type_from_decomp = task_type
    else:
        decomposer = Decomposer()
        decomp = decomposer.decompose(task_description)
        subtasks = decomp.subtasks
        task_type_from_decomp = decomp.task_type
        cost_tracker.record_decomposition(
            decomp.input_tokens, decomp.output_tokens, decomp.cost_usd
        )

    layers = Decomposer.topological_order(subtasks)

    ollama = OllamaClient(config.ollama_base_url)
    runner = MicroagentRunner(ollama)
    model = config.get_local_model(model_id)
    await ensure_capacity(ollama, model)

    accepted_outputs = {}
    per_subtask = {}

    for layer in layers:
        for subtask in layer:
            logger.info("Subtask %s: running %d inferences with %s", subtask.id, k, model.name)

            # Execute
            results = await runner.run_same_model(subtask, model, k, accepted_outputs)

            # Track cost
            cost_tracker.record_subtask(
                subtask_id=subtask.id,
                model_id=model_id,
                inference_count=len(results),
                total_duration_ms=sum(r.duration_ms for r in results),
                total_prompt_tokens=sum(r.prompt_tokens for r in results),
                total_completion_tokens=sum(r.completion_tokens for r in results),
            )

            # Filter
            candidates = [r.output for r in results]
            filtered, discard_log = filter_candidates(
                candidates, task_type, subtask.max_lines, subtask.prompt
            )

            if not filtered:
                logger.warning("All candidates filtered for subtask %s", subtask.id)
                # Use best unfiltered candidate as fallback
                filtered = candidates[:1]

            # Vote
            winner, vote_details = hybrid_vote(
                filtered,
                task_type=task_type,
                test_assertions=subtask.tests,
                task_description=subtask.prompt,
            )

            accepted_outputs[subtask.id] = winner or ""
            per_subtask[subtask.id] = {
                "candidate_count": len(candidates),
                "filtered_count": len(filtered),
                "discard_log": discard_log,
                "vote_details": vote_details,
            }

    # Step 5: Assemble
    subtask_order = [s.id for layer in layers for s in layer]
    assembly = assemble_and_test(
        accepted_outputs, subtask_order, task_type, integration_test_file
    )

    return MDAPResult(
        task_name=task_name,
        approach="same_model",
        model_id=model_id,
        k=k,
        task_type=task_type,
        decomposition_subtask_count=len(subtasks),
        per_subtask_results=per_subtask,
        assembled_output=assembly.assembled_code,
        integration_test_passed=assembly.integration_test_passed,
        integration_test_output=assembly.integration_test_output,
        cost_summary=cost_tracker.get_summary(),
        voting_details={},
        timestamp=datetime.utcnow().isoformat(),
    )


async def run_mdap_cross_model(
    task_description: str,
    task_name: str,
    task_type: str,
    config: Config,
    integration_test_file: str | None = None,
    pre_decomposed: list[SubTask] | None = None,
    model_subset: list[str] | None = None,
    ensemble_name: str | None = None,
) -> MDAPResult:
    """Run full MDAP pipeline with cross-model ensemble voting.

    Args:
        model_subset: List of model IDs to include. If None, uses all local models.
        ensemble_name: Label for this ensemble combo (e.g. "fast_trio").
    """
    cost_tracker = CostTracker(config)

    # Step 1: Decompose
    if pre_decomposed:
        subtasks = pre_decomposed
    else:
        decomposer = Decomposer()
        decomp = decomposer.decompose(task_description)
        subtasks = decomp.subtasks
        cost_tracker.record_decomposition(
            decomp.input_tokens, decomp.output_tokens, decomp.cost_usd
        )

    layers = Decomposer.topological_order(subtasks)

    # Resolve model subset
    if model_subset:
        models = [m for m in config.local_models if m.id in model_subset]
    else:
        models = config.local_models
    combo_label = ensemble_name or "all_models"

    ollama = OllamaClient(config.ollama_base_url)
    runner = MicroagentRunner(ollama)

    accepted_outputs = {}
    per_subtask = {}

    for layer in layers:
        for subtask in layer:
            logger.info("Subtask %s: running ensemble [%s]", subtask.id, combo_label)

            results = await runner.run_cross_model(
                subtask, models, accepted_outputs
            )

            cost_tracker.record_subtask(
                subtask_id=subtask.id,
                model_id=f"ensemble_{combo_label}",
                inference_count=len(results),
                total_duration_ms=sum(r.duration_ms for r in results),
                total_prompt_tokens=sum(r.prompt_tokens for r in results),
                total_completion_tokens=sum(r.completion_tokens for r in results),
            )

            candidates = [r.output for r in results]
            filtered, discard_log = filter_candidates(
                candidates, task_type, subtask.max_lines, subtask.prompt
            )

            if not filtered:
                filtered = candidates[:1]

            winner, vote_details = hybrid_vote(
                filtered,
                task_type=task_type,
                test_assertions=subtask.tests,
                task_description=subtask.prompt,
            )

            accepted_outputs[subtask.id] = winner or ""
            per_subtask[subtask.id] = {
                "candidate_count": len(candidates),
                "filtered_count": len(filtered),
                "discard_log": discard_log,
                "vote_details": vote_details,
                "model_results": [
                    {"model": r.model_name, "duration_ms": r.duration_ms}
                    for r in results
                ],
            }

    subtask_order = [s.id for layer in layers for s in layer]
    assembly = assemble_and_test(
        accepted_outputs, subtask_order, task_type, integration_test_file
    )

    return MDAPResult(
        task_name=task_name,
        approach=f"cross_model_{combo_label}",
        model_id=",".join(m.id for m in models),
        k=len(models),
        task_type=task_type,
        decomposition_subtask_count=len(subtasks),
        per_subtask_results=per_subtask,
        assembled_output=assembly.assembled_code,
        integration_test_passed=assembly.integration_test_passed,
        integration_test_output=assembly.integration_test_output,
        cost_summary=cost_tracker.get_summary(),
        voting_details={},
        timestamp=datetime.utcnow().isoformat(),
    )


def save_mdap_result(result: MDAPResult) -> Path:
    """Save MDAP result to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = (
        f"mdap_{result.task_name}_{result.approach}"
        f"{'_' + result.model_id.replace(':', '_') if result.model_id else ''}"
        f"_k{result.k}_{result.timestamp.replace(':', '-')}.json"
    )
    path = RESULTS_DIR / filename
    with open(path, "w") as f:
        json.dump(asdict(result), f, indent=2, default=str)
    return path


async def run_mdap_benchmark(
    task_yaml_path: str | Path,
    config: Config | None = None,
    k_values: list[int] | None = None,
) -> list[MDAPResult]:
    """Run the full MDAP benchmark for a task: same-model for each model + cross-model."""
    config = config or load_config()
    k_values = k_values or [config.test_params.mdap_k, config.test_params.mdap_k_sensitivity]

    task_yaml = Path(task_yaml_path)
    with open(task_yaml) as f:
        task = yaml.safe_load(f)

    task_description = task["prompt"]
    task_name = task.get("name", task_yaml.stem)
    task_type = task.get("task_type", "code")
    integration_test = task.get("integration_test_file")

    results = []

    # Same-model voting for each local model, at each k value
    for model in config.local_models:
        for k in k_values:
            logger.info("=== MDAP same-model: %s, k=%d ===", model.name, k)
            result = await run_mdap_same_model(
                task_description, task_name, task_type,
                model.id, config, k, integration_test,
            )
            path = save_mdap_result(result)
            results.append(result)
            logger.info("Saved: %s", path.name)

    # Cross-model ensemble combos
    ensemble_combos = {
        "all_models": None,  # None = use all
        "fast_trio": [
            "gemma4:e4b", "qwen3.5:9b", "deepseek-coder:6.7b",
        ],
        "mid_tier": [
            "qwen3.5:9b", "deepseek-r1:14b", "mistral-small3.2",
        ],
        "heavy_hitters": [
            "gemma4:26b", "gemma4:31b", "qwen3.5:27b",
        ],
        "best_of_breed": [
            "gemma4:26b", "qwen3.5:9b", "deepseek-r1:14b",
        ],
        "code_specialists": [
            "deepseek-coder:6.7b", "deepseek-r1:14b", "gemma4:26b",
        ],
    }

    for combo_name, model_ids in ensemble_combos.items():
        logger.info("=== MDAP ensemble: %s ===", combo_name)
        try:
            result = await run_mdap_cross_model(
                task_description, task_name, task_type,
                config, integration_test,
                model_subset=model_ids,
                ensemble_name=combo_name,
            )
            path = save_mdap_result(result)
            results.append(result)
            logger.info("Saved: %s", path.name)
        except Exception as e:
            logger.error("Ensemble %s failed: %s", combo_name, e)

    return results
