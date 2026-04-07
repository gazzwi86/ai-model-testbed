"""Run N independent inferences of a subtask against local models via Ollama.

Supports both same-model (k inferences of one model) and cross-model
(one inference per model) execution patterns.
"""

import logging
from dataclasses import dataclass

from harness.ollama_client import OllamaClient
from harness.model_lifecycle import ensure_capacity
from harness.config_loader import LocalModel
from .decomposer import SubTask

logger = logging.getLogger(__name__)


@dataclass
class MicroagentResult:
    subtask_id: str
    model_id: str
    model_name: str
    output: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: float
    tokens_per_second: float


class MicroagentRunner:
    def __init__(self, client: OllamaClient, temperature: float = 0.3):
        self.client = client
        self.temperature = temperature

    def _build_prompt(
        self,
        subtask: SubTask,
        prior_outputs: dict[str, str] | None = None,
    ) -> str:
        """Build the full prompt for a microagent including dependency context."""
        parts = []

        if prior_outputs and subtask.dependencies:
            parts.append("## Context from prior steps\n")
            for dep_id in subtask.dependencies:
                if dep_id in prior_outputs:
                    parts.append(f"### {dep_id}\n```python\n{prior_outputs[dep_id]}\n```\n")

        parts.append("## Your task\n")
        parts.append(subtask.prompt)

        if subtask.interface_contract:
            parts.append("\n\n## Interface contract")
            for key, val in subtask.interface_contract.items():
                parts.append(f"\n- {key}: {val}")

        if subtask.tests:
            parts.append("\n\n## Test assertions your code must pass")
            for test in subtask.tests:
                parts.append(f"\n- `{test}`")

        parts.append("\n\nReturn ONLY the code, no explanations.")

        return "\n".join(parts)

    async def run_single(
        self,
        subtask: SubTask,
        model: LocalModel,
        prior_outputs: dict[str, str] | None = None,
    ) -> MicroagentResult:
        """Run one inference of a subtask on one model."""
        prompt = self._build_prompt(subtask, prior_outputs)

        response = await self.client.chat(
            model=model.id,
            prompt=prompt,
            temperature=self.temperature,
            num_ctx=model.num_ctx,
        )

        return MicroagentResult(
            subtask_id=subtask.id,
            model_id=model.id,
            model_name=model.name,
            output=response.content,
            prompt_tokens=response.prompt_eval_count,
            completion_tokens=response.eval_count,
            duration_ms=response.total_duration_ms,
            tokens_per_second=response.tokens_per_second,
        )

    async def run_same_model(
        self,
        subtask: SubTask,
        model: LocalModel,
        k: int = 5,
        prior_outputs: dict[str, str] | None = None,
    ) -> list[MicroagentResult]:
        """Run k independent inferences of the same model (MAKER-style)."""
        logger.info(
            "Running %d inferences of %s for subtask %s",
            k, model.name, subtask.id,
        )
        # Run sequentially — same model can't truly parallelise on one GPU
        results = []
        for i in range(k):
            result = await self.run_single(subtask, model, prior_outputs)
            results.append(result)
            logger.debug("  Inference %d/%d complete (%.0fms)", i + 1, k, result.duration_ms)
        return results

    async def run_cross_model(
        self,
        subtask: SubTask,
        models: list[LocalModel],
        prior_outputs: dict[str, str] | None = None,
    ) -> list[MicroagentResult]:
        """Run one inference per model (cross-model ensemble).

        Models are run sequentially due to memory constraints — only one
        large model can be loaded at a time on 24GB.
        """
        logger.info(
            "Running cross-model ensemble (%d models) for subtask %s",
            len(models), subtask.id,
        )
        results = []
        for model in models:
            await ensure_capacity(self.client, model)
            result = await self.run_single(subtask, model, prior_outputs)
            results.append(result)
            logger.debug(
                "  %s complete (%.0fms, %.1f tok/s)",
                model.name, result.duration_ms, result.tokens_per_second,
            )
        return results
