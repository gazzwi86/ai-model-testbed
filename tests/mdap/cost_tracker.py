"""Track costs across the MDAP pipeline.

Tracks decomposition cost (Opus API), microagent cost (local inference),
and voting cost (LLM judge for pairwise ranking).
"""

from dataclasses import dataclass, field
from harness.config_loader import Config


@dataclass
class SubtaskCost:
    subtask_id: str
    model_id: str
    inference_count: int
    total_duration_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    local_cost_usd: float


@dataclass
class MDAPCostReport:
    decomposition_cost_usd: float = 0.0
    decomposition_tokens: int = 0
    subtask_costs: list[SubtaskCost] = field(default_factory=list)
    voting_cost_usd: float = 0.0
    voting_api_calls: int = 0
    total_local_inference_ms: float = 0.0
    total_local_inferences: int = 0

    @property
    def total_microagent_cost_usd(self) -> float:
        return sum(sc.local_cost_usd for sc in self.subtask_costs)

    @property
    def total_cost_usd(self) -> float:
        return (
            self.decomposition_cost_usd
            + self.total_microagent_cost_usd
            + self.voting_cost_usd
        )

    def equivalent_frontier_cost(self, config: Config) -> dict[str, float]:
        """Compute what this task would have cost on each frontier model."""
        total_tokens = sum(
            sc.total_prompt_tokens + sc.total_completion_tokens
            for sc in self.subtask_costs
        ) + self.decomposition_tokens

        costs = {}
        for model in config.frontier_models:
            # Rough split: 60% input, 40% output
            input_tokens = int(total_tokens * 0.6)
            output_tokens = int(total_tokens * 0.4)
            cost = (
                (input_tokens / 1_000_000) * model.input_price_per_mtok
                + (output_tokens / 1_000_000) * model.output_price_per_mtok
            )
            costs[model.name] = cost
        return costs

    def summary(self, config: Config) -> dict:
        frontier_costs = self.equivalent_frontier_cost(config)
        return {
            "decomposition_cost_usd": round(self.decomposition_cost_usd, 6),
            "microagent_cost_usd": round(self.total_microagent_cost_usd, 6),
            "voting_cost_usd": round(self.voting_cost_usd, 6),
            "total_mdap_cost_usd": round(self.total_cost_usd, 6),
            "total_local_inferences": self.total_local_inferences,
            "total_local_inference_ms": round(self.total_local_inference_ms, 1),
            "equivalent_frontier_costs": {
                k: round(v, 6) for k, v in frontier_costs.items()
            },
            "savings_vs_frontier": {
                k: round(v / self.total_cost_usd, 1) if self.total_cost_usd > 0 else 0
                for k, v in frontier_costs.items()
            },
        }


class CostTracker:
    def __init__(self, config: Config):
        self.config = config
        self.report = MDAPCostReport()

    def record_decomposition(self, input_tokens: int, output_tokens: int, cost_usd: float):
        self.report.decomposition_cost_usd = cost_usd
        self.report.decomposition_tokens = input_tokens + output_tokens

    def record_subtask(
        self,
        subtask_id: str,
        model_id: str,
        inference_count: int,
        total_duration_ms: float,
        total_prompt_tokens: int,
        total_completion_tokens: int,
    ):
        local_cost = (total_duration_ms / 1000) * self.config.local_cost.cost_per_second_usd

        self.report.subtask_costs.append(SubtaskCost(
            subtask_id=subtask_id,
            model_id=model_id,
            inference_count=inference_count,
            total_duration_ms=total_duration_ms,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            local_cost_usd=local_cost,
        ))
        self.report.total_local_inference_ms += total_duration_ms
        self.report.total_local_inferences += inference_count

    def record_voting(self, api_calls: int, cost_usd: float):
        self.report.voting_cost_usd += cost_usd
        self.report.voting_api_calls += api_calls

    def get_summary(self) -> dict:
        return self.report.summary(self.config)
