"""Main test orchestrator.

Usage:
  python -m harness.runner                            # Run all
  python -m harness.runner --category code_gen        # One category
  python -m harness.runner --model gemma4:e4b         # One model
  python -m harness.runner --tier simple              # One tier
  python -m harness.runner --mdap-only                # MDAP tests only
  python -m harness.runner --local-only               # Skip frontier models
  python -m harness.runner --frontier-only             # Skip local models
  python -m harness.runner --resume                   # Skip existing results
"""

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from .config_loader import load_config, Config, LocalModel, FrontierModel
from .ollama_client import OllamaClient
from .claude_client import ClaudeClient
from .model_lifecycle import ensure_capacity
from .metrics import metrics_from_ollama, metrics_from_claude
from .paths import PROMPTS_DIR, RAW_RESULTS_DIR

logger = logging.getLogger(__name__)


def _result_prefix(category: str, tier: str, model_id: str, run_idx: int) -> str:
    """Return the deterministic prefix of a result filename (without timestamp)."""
    return f"{category}_{tier}_{model_id.replace(':', '_')}_run{run_idx}_"


def _result_exists(category: str, tier: str, model_id: str, run_idx: int) -> bool:
    """Check whether a result file already exists for this test run."""
    prefix = _result_prefix(category, tier, model_id, run_idx)
    return any(RAW_RESULTS_DIR.glob(f"{prefix}*.json"))


def load_prompts(
    category: str | None = None,
    tier: str | None = None,
) -> list[dict]:
    """Load prompt YAML files, optionally filtered by category/tier."""
    prompts = []
    for cat_dir in sorted(PROMPTS_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        if category and cat_dir.name != category:
            continue
        for yaml_file in sorted(cat_dir.glob("*.yaml")):
            with open(yaml_file) as f:
                prompt = yaml.safe_load(f)
            if tier and prompt.get("tier") != tier:
                continue
            prompt["_file"] = str(yaml_file)
            prompts.append(prompt)
    return prompts


async def run_local_test(
    client: OllamaClient,
    model: LocalModel,
    prompt: dict,
    run_idx: int,
    config: Config,
) -> dict:
    """Run a single test against a local Ollama model."""
    temperature = prompt.get("temperature", config.ollama_default_temperature)
    max_tokens = prompt.get("max_output_tokens", None)

    response = await client.chat(
        model=model.id,
        prompt=prompt["prompt"],
        temperature=temperature,
        num_ctx=model.num_ctx,
        max_tokens=max_tokens,
    )

    metrics = metrics_from_ollama(
        response=response,
        config=config,
        category=prompt["category"],
        tier=prompt["tier"],
        run_idx=run_idx,
        model_name=model.name,
        model_id=model.id,
    )

    return {
        "model": model.name,
        "model_id": model.id,
        "backend": "ollama",
        "category": prompt["category"],
        "tier": prompt["tier"],
        "test_name": prompt.get("name", "unknown"),
        "run_idx": run_idx,
        "timestamp": datetime.utcnow().isoformat(),
        "response_text": response.content,
        "metrics": asdict(metrics),
        "scores": None,
    }


async def run_frontier_test(
    client: ClaudeClient,
    model: FrontierModel,
    prompt: dict,
    run_idx: int,
    config: Config,
) -> dict:
    """Run a single test against a Claude frontier model."""
    temperature = prompt.get("temperature", config.test_params.temperature_code)
    max_tokens = prompt.get("max_output_tokens", 4096)

    response = await client.chat(
        model=model.id,
        prompt=prompt["prompt"],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    metrics = metrics_from_claude(
        response=response,
        model=model,
        category=prompt["category"],
        tier=prompt["tier"],
        run_idx=run_idx,
    )

    return {
        "model": model.name,
        "model_id": model.id,
        "backend": "claude",
        "category": prompt["category"],
        "tier": prompt["tier"],
        "test_name": prompt.get("name", "unknown"),
        "run_idx": run_idx,
        "timestamp": datetime.utcnow().isoformat(),
        "response_text": response.content,
        "metrics": asdict(metrics),
        "scores": None,
    }


def save_result(result: dict) -> Path:
    """Save a single test result to JSON."""
    filename = (
        f"{result['category']}_{result['tier']}_{result['model_id'].replace(':', '_')}"
        f"_run{result['run_idx']}_{result['timestamp'].replace(':', '-')}.json"
    )
    path = RAW_RESULTS_DIR / filename
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    return path


async def run_mdap(config: Config) -> None:
    """Run MDAP benchmark tests."""
    from tests.mdap.runner import run_mdap_benchmark
    from pathlib import Path

    mdap_tasks_dir = Path(__file__).parent.parent / "tests" / "mdap" / "tasks"
    for task_dir in sorted(mdap_tasks_dir.iterdir()):
        task_yaml = task_dir / "task.yaml"
        if task_yaml.exists():
            logger.info("=== MDAP: %s ===", task_dir.name)
            try:
                results = await run_mdap_benchmark(task_yaml, config)
                logger.info("  Completed %d MDAP runs for %s", len(results), task_dir.name)
            except Exception as e:
                logger.error("  MDAP failed for %s: %s", task_dir.name, e)


async def run_all(args: argparse.Namespace) -> None:
    config = load_config()

    if args.mdap_only:
        await run_mdap(config)
        return

    prompts = load_prompts(category=args.category, tier=args.tier)

    if not prompts:
        logger.error("No prompts found matching filters")
        return

    logger.info("Loaded %d prompt(s)", len(prompts))

    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    ollama = OllamaClient(config.ollama_base_url)
    claude = ClaudeClient()
    completed_count = 0
    skipped_count = 0

    # Determine which models to run
    local_models = config.local_models
    frontier_models = config.frontier_models

    if args.model:
        local_models = [m for m in local_models if m.id == args.model]
        frontier_models = [m for m in frontier_models if m.id == args.model]

    if args.local_only:
        frontier_models = []
    if args.frontier_only:
        local_models = []

    # Run local models
    for model in local_models:
        logger.info("=== Testing %s ===", model.name)

        # Log currently loaded models (memory check)
        loaded = await ollama.list_running()
        if loaded:
            names = [m.get("name", "") for m in loaded]
            logger.info("Models currently in memory: %s", ", ".join(names))

        await ensure_capacity(ollama, model)

        for prompt in prompts:
            for run_idx in range(config.test_params.runs_per_test):
                # --resume: skip if result already exists
                if args.resume and _result_exists(
                    prompt["category"], prompt["tier"], model.id, run_idx
                ):
                    skipped_count += 1
                    logger.info(
                        "  SKIP %s/%s run %d (result exists)",
                        prompt["category"],
                        prompt["tier"],
                        run_idx + 1,
                    )
                    continue

                logger.info(
                    "  %s/%s run %d/%d",
                    prompt["category"],
                    prompt["tier"],
                    run_idx + 1,
                    config.test_params.runs_per_test,
                )
                try:
                    result = await run_local_test(
                        ollama, model, prompt, run_idx, config
                    )
                    path = save_result(result)
                    completed_count += 1
                    logger.info("    Saved: %s", path.name)
                except Exception as e:
                    logger.error("    FAILED: %s", e)

        # Explicitly unload the model after its tests complete
        logger.info("Unloading %s after tests", model.id)
        await ollama.unload(model.id)

    # Run frontier models
    for model in frontier_models:
        logger.info("=== Testing %s ===", model.name)

        for prompt in prompts:
            for run_idx in range(config.test_params.runs_per_test):
                # --resume: skip if result already exists
                if args.resume and _result_exists(
                    prompt["category"], prompt["tier"], model.id, run_idx
                ):
                    skipped_count += 1
                    logger.info(
                        "  SKIP %s/%s run %d (result exists)",
                        prompt["category"],
                        prompt["tier"],
                        run_idx + 1,
                    )
                    continue

                logger.info(
                    "  %s/%s run %d/%d",
                    prompt["category"],
                    prompt["tier"],
                    run_idx + 1,
                    config.test_params.runs_per_test,
                )
                try:
                    result = await run_frontier_test(
                        claude, model, prompt, run_idx, config
                    )
                    path = save_result(result)
                    completed_count += 1
                    logger.info("    Saved: %s", path.name)
                except Exception as e:
                    logger.error("    FAILED: %s", e)

    await ollama.close()
    logger.info(
        "Completed %d test runs (%d skipped via --resume)", completed_count, skipped_count
    )


def main():
    parser = argparse.ArgumentParser(description="Local LLM Benchmark Runner")
    parser.add_argument("--category", type=str, help="Test category filter")
    parser.add_argument("--model", type=str, help="Model ID filter")
    parser.add_argument("--tier", type=str, help="Tier filter (simple/medium/hard)")
    parser.add_argument("--mdap-only", action="store_true", help="Run MDAP tests only")
    parser.add_argument("--local-only", action="store_true", help="Skip frontier models")
    parser.add_argument("--frontier-only", action="store_true", help="Skip local models")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip tests whose result files already exist in results/raw/",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(run_all(args))


if __name__ == "__main__":
    main()
