"""Async wrapper around the Anthropic Claude API."""

import time
from dataclasses import dataclass

import anthropic


@dataclass
class ClaudeResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_duration_ms: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ClaudeClient:
    def __init__(self):
        self.client = anthropic.Anthropic()

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

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        # Use sync client in async context — anthropic SDK handles this fine
        # for our throughput needs. Switch to AsyncAnthropic if needed.
        response = self.client.messages.create(**kwargs)

        elapsed_ms = (time.monotonic() - start) * 1000

        return ClaudeResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_duration_ms=elapsed_ms,
        )
