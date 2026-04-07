"""Metrics computation for local and frontier inference costs."""

from dataclasses import dataclass, field
from datetime import datetime

from .config_loader import Config, FrontierModel
from .ollama_client import OllamaResponse
from .claude_client import ClaudeResponse


@dataclass
class TestMetrics:
    model_name: str
    model_id: str
    backend: str  # "ollama" or "claude"
    category: str
    tier: str
    run_idx: int
    timestamp: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    ttft_ms: float = 0.0
    total_duration_ms: float = 0.0
    tokens_per_second: float = 0.0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def compute_local_cost(total_duration_ns: int, config: Config) -> float:
    """Compute the amortised local cost for a single inference."""
    seconds = total_duration_ns / 1e9
    return seconds * config.local_cost.cost_per_second_usd


def compute_frontier_cost(
    input_tokens: int,
    output_tokens: int,
    model: FrontierModel,
) -> float:
    """Compute API cost for a frontier model call."""
    input_cost = (input_tokens / 1_000_000) * model.input_price_per_mtok
    output_cost = (output_tokens / 1_000_000) * model.output_price_per_mtok
    return input_cost + output_cost


def metrics_from_ollama(
    response: OllamaResponse,
    config: Config,
    category: str,
    tier: str,
    run_idx: int,
    model_name: str,
    model_id: str,
) -> TestMetrics:
    return TestMetrics(
        model_name=model_name,
        model_id=model_id,
        backend="ollama",
        category=category,
        tier=tier,
        run_idx=run_idx,
        timestamp=datetime.utcnow().isoformat(),
        prompt_tokens=response.prompt_eval_count,
        completion_tokens=response.eval_count,
        ttft_ms=response.ttft_ms,
        total_duration_ms=response.total_duration_ms,
        tokens_per_second=response.tokens_per_second,
        cost_usd=compute_local_cost(response.total_duration_ns, config),
    )


def metrics_from_claude(
    response: ClaudeResponse,
    model: FrontierModel,
    category: str,
    tier: str,
    run_idx: int,
) -> TestMetrics:
    return TestMetrics(
        model_name=model.name,
        model_id=model.id,
        backend="claude",
        category=category,
        tier=tier,
        run_idx=run_idx,
        timestamp=datetime.utcnow().isoformat(),
        prompt_tokens=response.input_tokens,
        completion_tokens=response.output_tokens,
        total_duration_ms=response.total_duration_ms,
        cost_usd=compute_frontier_cost(
            response.input_tokens, response.output_tokens, model
        ),
    )
