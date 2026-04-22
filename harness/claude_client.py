"""Claude API client using claude-agent-sdk.

Uses the Claude Code CLI under the hood, which supports OAuth tokens
(CLAUDE_CODE_OAUTH_TOKEN) from Claude subscriptions. No separate
console API key needed.
"""

import time
import logging
from dataclasses import dataclass

import claude_agent_sdk

logger = logging.getLogger(__name__)


@dataclass
class ClaudeResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_duration_ms: float
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ClaudeClient:
    def __init__(self):
        pass

    async def chat(
        self,
        model: str,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        system: str | None = None,
    ) -> ClaudeResponse:
        start = time.monotonic()

        options = claude_agent_sdk.ClaudeAgentOptions(
            model=model,
            max_turns=1,
            permission_mode="bypassPermissions",
            system_prompt=system,
        )

        result_text = ""
        input_tokens = 0
        output_tokens = 0
        result_model = model
        cost_usd = 0.0

        async for event in claude_agent_sdk.query(
            prompt=prompt,
            options=options,
        ):
            if isinstance(event, claude_agent_sdk.AssistantMessage):
                for block in event.content:
                    if isinstance(block, claude_agent_sdk.TextBlock):
                        result_text += block.text
                if event.model:
                    result_model = event.model

            elif isinstance(event, claude_agent_sdk.ResultMessage):
                # ResultMessage has the final result text and usage stats
                if event.result and not result_text:
                    result_text = event.result
                if event.usage:
                    input_tokens = getattr(event.usage, 'input_tokens', 0) or 0
                    output_tokens = getattr(event.usage, 'output_tokens', 0) or 0
                if event.total_cost_usd:
                    cost_usd = event.total_cost_usd

        elapsed_ms = (time.monotonic() - start) * 1000

        if not result_text:
            logger.warning("Empty response from Claude %s", model)

        return ClaudeResponse(
            content=result_text,
            model=result_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_duration_ms=elapsed_ms,
            cost_usd=cost_usd,
        )
