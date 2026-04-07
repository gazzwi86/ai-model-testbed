"""Compute cost comparisons between local, frontier, and MDAP approaches."""

import json
import logging
from collections import defaultdict
from pathlib import Path

from harness.paths import PROJECT_ROOT
from .utils import load_scored_results

logger = logging.getLogger(__name__)


def compute_cost_comparison(results: list[dict]) -> dict:
    """Compute per-category, per-tier cost comparisons."""
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for r in results:
        category = r["category"]
        tier = r["tier"]
        model = r["model"]
        cost = r["metrics"].get("cost_usd", 0)
        grouped[category][tier][model].append(cost)

    comparison = {}
    for cat, tiers in grouped.items():
        comparison[cat] = {}
        for tier, models in tiers.items():
            comparison[cat][tier] = {}
            for model, costs in models.items():
                avg_cost = sum(costs) / len(costs) if costs else 0
                comparison[cat][tier][model] = {
                    "avg_cost_usd": round(avg_cost, 8),
                    "total_cost_usd": round(sum(costs), 8),
                    "runs": len(costs),
                }
    return comparison


def compute_savings_matrix(comparison: dict) -> dict:
    """Compute savings ratios: how much cheaper is each model vs Sonnet."""
    savings = {}
    for cat, tiers in comparison.items():
        savings[cat] = {}
        for tier, models in tiers.items():
            sonnet_cost = None
            for model_name, data in models.items():
                if "Sonnet" in model_name:
                    sonnet_cost = data["avg_cost_usd"]
                    break

            savings[cat][tier] = {}
            if sonnet_cost and sonnet_cost > 0:
                for model_name, data in models.items():
                    model_cost = data["avg_cost_usd"]
                    if model_cost > 0:
                        ratio = sonnet_cost / model_cost
                        savings[cat][tier][model_name] = round(ratio, 1)
                    else:
                        savings[cat][tier][model_name] = float("inf")
    return savings


def generate_report():
    """Generate the full cost comparison report."""
    results = load_scored_results()
    if not results:
        logger.warning("No scored results found")
        return

    comparison = compute_cost_comparison(results)
    savings = compute_savings_matrix(comparison)

    report = {
        "cost_comparison": comparison,
        "savings_vs_sonnet": savings,
    }

    out_path = PROJECT_ROOT / "results" / "cost_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Cost report saved to %s", out_path)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_report()
