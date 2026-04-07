"""Async wrapper around Ollama's native HTTP API."""

import aiohttp
from dataclasses import dataclass


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

        session = await self._get_session()
        async with session.post(
            f"{self.base_url}/api/chat",
            json=payload,
        ) as resp:
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
