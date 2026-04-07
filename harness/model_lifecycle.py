"""Manage model loading/unloading to stay within 24GB memory."""

import asyncio
import logging

from .ollama_client import OllamaClient
from .config_loader import LocalModel

logger = logging.getLogger(__name__)

LARGE_MODEL_THRESHOLD_GB = 10


async def ensure_capacity(
    client: OllamaClient,
    target: LocalModel,
) -> None:
    """Unload other large models if the target model is large."""
    if target.size_gb < LARGE_MODEL_THRESHOLD_GB:
        return

    loaded = await client.list_running()
    for model in loaded:
        model_name = model.get("name", "")
        if model_name != target.id:
            logger.info("Unloading %s to make room for %s", model_name, target.id)
            await client.unload(model_name)
            await asyncio.sleep(2)


async def unload_all(client: OllamaClient) -> None:
    """Unload all currently loaded models."""
    loaded = await client.list_running()
    for model in loaded:
        model_name = model.get("name", "")
        logger.info("Unloading %s", model_name)
        await client.unload(model_name)
        await asyncio.sleep(1)
