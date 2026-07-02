"""FastAPI app for the mock AI worker.

Starts the RabbitMQ consumer as a background asyncio task on startup and exposes
a /health endpoint. This is a drop-in replacement for the real ai-worker used
in E2E testing when Ollama is unavailable.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import config, consumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the consumer on startup, cancel it on shutdown."""
    global _consumer_task
    logger.info("Starting mock AI worker consumer (useLLM=%s)", config.USE_REAL_LLM)
    _consumer_task = asyncio.create_task(consumer.run())
    try:
        yield
    finally:
        if _consumer_task is not None:
            _consumer_task.cancel()
            try:
                await _consumer_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Mock AI Worker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """Report worker health. Always UP in mock mode."""
    return {"status": "UP", "mode": "mock", "useLLM": config.USE_REAL_LLM}
