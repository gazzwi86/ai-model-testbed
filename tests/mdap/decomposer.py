"""Task decomposition using Claude Opus 4.6.

Breaks a complex task into atomic subtasks with interface contracts,
test assertions, and dependency ordering.
"""

import json
import logging
from dataclasses import dataclass, field

import claude_agent_sdk

logger = logging.getLogger(__name__)

DECOMPOSITION_PROMPT = """\
You are a task decomposition engine. Your job is to break a complex task into \
the smallest possible independent subtasks, following the Maximal Agentic \
Decomposition (MAD) principle.

## Rules

1. Each subtask must be self-contained: a focused microagent should be able to \
complete it with ONLY the subtask prompt and outputs from prior dependencies.
2. Each subtask must have explicit interface contracts: what it receives, what \
it produces.
3. Each subtask must include test assertions that can verify correctness.
4. Minimise dependencies between subtasks. Prefer independent subtasks.
5. For code tasks: each subtask should produce one function or class.
6. For text tasks: each subtask should produce one section or analysis unit.

## Output Format

Return a JSON object with this structure:
```json
{{
  "task_type": "code" | "text",
  "subtasks": [
    {{
      "id": "unique_snake_case_id",
      "prompt": "Complete, self-contained prompt for a microagent",
      "dependencies": ["id_of_prior_subtask"],
      "inputs": "Description of inputs from dependencies (null if none)",
      "outputs": "Description of what this subtask produces",
      "tests": ["assert statement 1", "assert statement 2"],
      "max_lines": 50,
      "interface_contract": {{
        "function_name": "name (for code tasks)",
        "signature": "full signature (for code tasks)",
        "return_type": "return type (for code tasks)"
      }}
    }}
  ]
}}
```

## Task to Decompose

{task_description}
"""


@dataclass
class SubTask:
    id: str
    prompt: str
    dependencies: list[str] = field(default_factory=list)
    inputs: str | None = None
    outputs: str = ""
    tests: list[str] = field(default_factory=list)
    max_lines: int = 50
    interface_contract: dict = field(default_factory=dict)


@dataclass
class DecompositionResult:
    task_type: str
    subtasks: list[SubTask]
    raw_response: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class Decomposer:
    def __init__(
        self,
        model: str = "claude-opus-4-6",
        input_price_per_mtok: float = 5.00,
        output_price_per_mtok: float = 25.00,
    ):
        self.model = model
        self.input_price_per_mtok = input_price_per_mtok
        self.output_price_per_mtok = output_price_per_mtok

    async def decompose(self, task_description: str) -> DecompositionResult:
        """Decompose a task into subtasks using Opus."""
        prompt_text = DECOMPOSITION_PROMPT.format(task_description=task_description)

        options = claude_agent_sdk.ClaudeAgentOptions(
            model=self.model,
            max_turns=1,
            permission_mode="bypassPermissions",
        )

        raw = ""
        input_tokens = 0
        output_tokens = 0
        async for event in claude_agent_sdk.query(prompt=prompt_text, options=options):
            if isinstance(event, claude_agent_sdk.AssistantMessage):
                for block in event.content:
                    if isinstance(block, claude_agent_sdk.TextBlock):
                        raw += block.text
            elif isinstance(event, claude_agent_sdk.ResultMessage):
                if event.result and not raw:
                    raw = event.result
                if event.usage:
                    input_tokens = getattr(event.usage, 'input_tokens', 0) or 0
                    output_tokens = getattr(event.usage, 'output_tokens', 0) or 0
        from harness.metrics import compute_frontier_cost
        from harness.config_loader import FrontierModel
        _model = FrontierModel(
            id=self.model, name=self.model,
            input_price_per_mtok=self.input_price_per_mtok,
            output_price_per_mtok=self.output_price_per_mtok,
        )
        cost = compute_frontier_cost(input_tokens, output_tokens, _model)

        # Parse JSON from response (handle markdown code blocks)
        json_str = raw
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())

        subtasks = [
            SubTask(
                id=s["id"],
                prompt=s["prompt"],
                dependencies=s.get("dependencies", []),
                inputs=s.get("inputs"),
                outputs=s.get("outputs", ""),
                tests=s.get("tests", []),
                max_lines=s.get("max_lines", 50),
                interface_contract=s.get("interface_contract", {}),
            )
            for s in data["subtasks"]
        ]

        logger.info(
            "Decomposed into %d subtasks (cost: $%.4f)", len(subtasks), cost
        )

        return DecompositionResult(
            task_type=data.get("task_type", "code"),
            subtasks=subtasks,
            raw_response=raw,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    @staticmethod
    def topological_order(subtasks: list[SubTask]) -> list[list[SubTask]]:
        """Return subtasks grouped into dependency layers for parallel execution."""
        completed = set()
        remaining = {s.id: s for s in subtasks}
        layers = []

        while remaining:
            layer = []
            for sid, subtask in remaining.items():
                if all(dep in completed for dep in subtask.dependencies):
                    layer.append(subtask)

            if not layer:
                raise ValueError(
                    f"Circular dependency detected. Remaining: {list(remaining.keys())}"
                )

            for subtask in layer:
                del remaining[subtask.id]
                completed.add(subtask.id)
            layers.append(layer)

        return layers
