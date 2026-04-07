"""Manage model loading/unloading to stay within 24GB memory."""

import asyncio
import logging

from .ollama_client import OllamaClient
from .config_loader import LocalModel

logger = logging.getLogger(__name__)

LARGE_MODEL_THRESHOLD_GB = 10
UNLOAD_TIMEOUT_SECONDS = 30


async def _verify_unloaded(
    client: OllamaClient,
    model_name: str,
    timeout: float = UNLOAD_TIMEOUT_SECONDS,
) -> bool:
    """Poll list_running to verify a model has actually unloaded."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        loaded = await client.list_running()
        names = [m.get("name", "") for m in loaded]
        if model_name not in names:
            return True
        await asyncio.sleep(2)
    logger.warning(
        "Model %s did not unload within %ds -- continuing anyway",
        model_name,
        timeout,
    )
    return False


async def ensure_capacity(
    client: OllamaClient,
    target: LocalModel,
) -> None:
    """Unload other models to make room for the target model.

    For large models (>10GB), unload ALL other models to maximise
    available memory.  For smaller models, still log what is loaded.
    """
    loaded = await client.list_running()
    if loaded:
        names = [m.get("name", "") for m in loaded]
        logger.info("Currently loaded models: %s", ", ".join(names))

    if target.size_gb >= LARGE_MODEL_THRESHOLD_GB:
        # Large model -- aggressively free everything
        for model in loaded:
            model_name = model.get("name", "")
            if model_name == target.id:
                continue
            logger.info("Unloading %s to make room for %s", model_name, target.id)
            await client.unload(model_name)
            await _verify_unloaded(client, model_name)


async def unload_all(client: OllamaClient) -> None:
    """Unload all currently loaded models."""
    loaded = await client.list_running()
    for model in loaded:
        model_name = model.get("name", "")
        logger.info("Unloading %s", model_name)
        await client.unload(model_name)
        await _verify_unloaded(client, model_name)
