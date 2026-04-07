"""Async wrapper around Ollama's native HTTP API."""

import asyncio
import logging

import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OllamaResponse:
    content: str
    model: str
    prompt_eval_count: int
    eval_count: int
    prompt_eval_duration_ns: int
    eval_duration_ns: int
    total_duration_ns: int

    @property
    def tokens_per_second(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.eval_count / (self.eval_duration_ns / 1e9)

    @property
    def ttft_ms(self) -> float:
        return self.prompt_eval_duration_ns / 1e6

    @property
    def total_duration_ms(self) -> float:
        return self.total_duration_ns / 1e6


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=600),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def chat(
        self,
        model: str,
        prompt: str,
        *,
        temperature: float = 0.3,
        num_ctx: int = 8192,
        max_tokens: int | None = None,
        system: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> OllamaResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    if resp.status in (500, 502, 503):
                        body = await resp.text()
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message=f"Ollama server error {resp.status}: {body[:200]}",
                        )
                    resp.raise_for_status()
                    data = await resp.json()

                return OllamaResponse(
                    content=data["message"]["content"],
                    model=data.get("model", model),
                    prompt_eval_count=data.get("prompt_eval_count", 0),
                    eval_count=data.get("eval_count", 0),
                    prompt_eval_duration_ns=data.get("prompt_eval_duration", 0),
                    eval_duration_ns=data.get("eval_duration", 0),
                    total_duration_ns=data.get("total_duration", 0),
                )
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < max_retries:
                    wait = retry_delay * (2 ** attempt)
                    logger.warning(
                        "Ollama chat failed (attempt %d/%d), retrying in %.0fs: %s",
                        attempt + 1,
                        max_retries + 1,
                        wait,
                        e,
                    )
                    await asyncio.sleep(wait)

        raise last_error  # type: ignore[misc]

    async def list_running(self) -> list[dict]:
        session = await self._get_session()
        async with session.get(f"{self.base_url}/api/ps") as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("models", [])

    async def unload(self, model: str) -> None:
        session = await self._get_session()
        await session.post(
            f"{self.base_url}/api/chat",
            json={"model": model, "messages": [], "keep_alive": 0},
        )

    async def pull(self, model: str) -> None:
        session = await self._get_session()
        async with session.post(
            f"{self.base_url}/api/pull",
            json={"model": model, "stream": False},
            timeout=aiohttp.ClientTimeout(total=3600),
        ) as resp:
            resp.raise_for_status()
