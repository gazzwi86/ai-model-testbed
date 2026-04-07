"""Generate markdown comparison tables for the blog post.

Produces the routing matrix — the centrepiece of the article.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path

from harness.paths import PROJECT_ROOT
from .utils import load_scored_results

logger = logging.getLogger(__name__)

LOCAL_THRESHOLD = 80
HYBRID_THRESHOLD = 60


def compute_averages(results: list[dict]) -> dict:
    """Compute average scores per model, category, tier."""
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for r in results:
        key = (r["category"], r["tier"])
        model = r["model"]
        if r.get("scores"):
            for dim, score in r["scores"].items():
                if score is not None:
                    grouped[key][model][dim].append(score)

    averages = {}
    for key, models in grouped.items():
        averages[key] = {}
        for model, dims in models.items():
            averages[key][model] = {}
            for dim, scores in dims.items():
                averages[key][model][dim] = round(sum(scores) / len(scores), 1)
            # Composite score = mean of all dimensions
            all_scores = [s for s in averages[key][model].values()]
            if all_scores:
                averages[key][model]["composite"] = round(
                    sum(all_scores) / len(all_scores), 1
                )
    return averages


def generate_routing_matrix(results: list[dict]) -> str:
    """Generate the routing matrix markdown table."""
    averages = compute_averages(results)

    # Collect all models
    all_models = set()
    for key, models in averages.items():
        all_models.update(models.keys())

    # Identify local vs frontier
    local_models = sorted([m for m in all_models if "Claude" not in m])
    frontier_models = sorted([m for m in all_models if "Claude" in m])

    lines = ["# Routing Matrix\n"]
    lines.append("| Category | Tier | Best Local | Local Score | "
                 + " | ".join(frontier_models) + " | Verdict |")
    lines.append("|" + "---|" * (5 + len(frontier_models)))

    for (cat, tier), models in sorted(averages.items()):
        # Find best local model
        best_local = None
        best_local_score = -1
        for model in local_models:
            if model in models:
                score = models[model].get("composite", 0)
                if score > best_local_score:
                    best_local_score = score
                    best_local = model

        # Frontier scores
        frontier_scores = []
        for fm in frontier_models:
            if fm in models:
                frontier_scores.append(f"{models[fm].get('composite', '?')}")
            else:
                frontier_scores.append("—")

        # Verdict
        if best_local_score >= LOCAL_THRESHOLD:
            verdict = "Local"
        elif best_local_score >= HYBRID_THRESHOLD:
            verdict = "MDAP / Hybrid"
        else:
            verdict = "Frontier"

        lines.append(
            f"| {cat} | {tier} | {best_local or '—'} | "
            f"{best_local_score if best_local_score >= 0 else '—'} | "
            f"{' | '.join(frontier_scores)} | {verdict} |"
        )

    return "\n".join(lines)


def generate_strength_profiles(results: list[dict]) -> str:
    """Generate per-model strength profile tables showing sub-dimension scores."""
    averages = compute_averages(results)

    # Invert: model -> {(cat, tier): {dim: score}}
    model_profiles = defaultdict(dict)
    for key, models in averages.items():
        for model, dims in models.items():
            model_profiles[model][key] = dims

    lines = ["# Model Strength Profiles\n"]
    for model in sorted(model_profiles.keys()):
        lines.append(f"\n## {model}\n")
        profile = model_profiles[model]

        # Get all dimensions across categories
        all_dims = set()
        for dims in profile.values():
            all_dims.update(dims.keys())
        all_dims.discard("composite")
        all_dims = sorted(all_dims)

        lines.append("| Category | Tier | " + " | ".join(all_dims) + " | Composite |")
        lines.append("|" + "---|" * (3 + len(all_dims)))

        for (cat, tier), dims in sorted(profile.items()):
            dim_values = [str(dims.get(d, "—")) for d in all_dims]
            composite = dims.get("composite", "—")
            lines.append(f"| {cat} | {tier} | {' | '.join(dim_values)} | {composite} |")

    return "\n".join(lines)


def main():
    results = load_scored_results()
    if not results:
        logger.warning("No scored results found")
        return

    routing = generate_routing_matrix(results)
    profiles = generate_strength_profiles(results)

    out_dir = PROJECT_ROOT / "results"
    (out_dir / "routing_matrix.md").write_text(routing)
    (out_dir / "strength_profiles.md").write_text(profiles)
    logger.info("Generated routing_matrix.md and strength_profiles.md")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
