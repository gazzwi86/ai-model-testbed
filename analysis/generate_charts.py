"""Generate charts for the blog post.

- Radar charts: per-model strength profiles across sub-dimensions
- Bar charts: cost comparisons
- Line charts: MDAP quality vs k (vote count)
"""

import json
import logging
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from harness.paths import PROJECT_ROOT, CHARTS_DIR
from .utils import load_scored_results

logger = logging.getLogger(__name__)


def radar_chart(model_scores: dict[str, dict[str, float]], title: str, output_path: Path):
    """Create a radar chart comparing models across dimensions."""
    categories = sorted(
        set(dim for scores in model_scores.values() for dim in scores if dim != "composite")
    )
    if not categories:
        return

    n = len(categories)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    for model_name, scores in model_scores.items():
        values = [scores.get(cat, 0) for cat in categories]
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2, label=model_name)
        ax.fill(angles, values, alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=10)
    ax.set_ylim(0, 100)
    ax.set_title(title, size=16, y=1.08)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved radar chart: %s", output_path)


def cost_bar_chart(cost_data: dict[str, float], title: str, output_path: Path):
    """Create a bar chart comparing costs across models."""
    models = list(cost_data.keys())
    costs = list(cost_data.values())

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#4CAF50" if c < 0.01 else "#2196F3" if c < 0.05 else "#FF9800" for c in costs]
    bars = ax.bar(models, costs, color=colors)

    ax.set_ylabel("Cost (USD)")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=45)

    for bar, cost in zip(bars, costs):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"${cost:.4f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved cost chart: %s", output_path)


def mdap_quality_curve(mdap_results: list[dict], output_path: Path):
    """Plot quality vs k (vote count) for MDAP tests."""
    # Group by model
    model_data = defaultdict(lambda: {"k": [], "score": []})
    for r in mdap_results:
        model = r.get("model_id", "cross_model") or "cross_model"
        k = r.get("k", 0)
        # Use integration test pass as a proxy for quality
        score = 100 if r.get("integration_test_passed") else 0
        model_data[model]["k"].append(k)
        model_data[model]["score"].append(score)

    fig, ax = plt.subplots(figsize=(10, 6))
    for model, data in model_data.items():
        ax.plot(data["k"], data["score"], "o-", label=model, linewidth=2)

    ax.set_xlabel("k (votes per subtask)")
    ax.set_ylabel("Quality Score (%)")
    ax.set_title("MDAP Quality vs Vote Count")
    ax.legend()
    ax.set_ylim(0, 105)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved MDAP quality curve: %s", output_path)


def main():
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    results = load_scored_results()

    if not results:
        logger.warning("No scored results found")
        return

    # Aggregate scores per model across all categories
    model_avg_scores = defaultdict(lambda: defaultdict(list))
    model_costs = defaultdict(list)

    for r in results:
        model = r["model"]
        if r.get("scores"):
            for dim, score in r["scores"].items():
                if score is not None:
                    model_avg_scores[model][dim].append(score)
        if r.get("metrics", {}).get("cost_usd"):
            model_costs[model].append(r["metrics"]["cost_usd"])

    # Average scores
    avg_scores = {}
    for model, dims in model_avg_scores.items():
        avg_scores[model] = {
            dim: round(sum(scores) / len(scores), 1)
            for dim, scores in dims.items()
        }

    # Radar chart — all models
    radar_chart(avg_scores, "Model Strength Profiles", CHARTS_DIR / "radar_all_models.png")

    # Cost comparison
    avg_costs = {
        model: round(sum(costs) / len(costs), 6)
        for model, costs in model_costs.items()
    }
    cost_bar_chart(avg_costs, "Average Cost Per Test (USD)", CHARTS_DIR / "cost_comparison.png")

    # MDAP results (if any)
    mdap_dir = PROJECT_ROOT / "results" / "raw"
    mdap_results = []
    for path in mdap_dir.glob("mdap_*.json"):
        with open(path) as f:
            mdap_results.append(json.load(f))

    if mdap_results:
        mdap_quality_curve(mdap_results, CHARTS_DIR / "mdap_quality_curve.png")

    logger.info("All charts generated in %s", CHARTS_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
