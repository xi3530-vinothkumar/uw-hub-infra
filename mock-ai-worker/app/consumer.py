"""Async RabbitMQ consumer for the mock AI worker.

Mirrors the real worker's topology contract: prefetch=1, dispatch by taskType,
publish a ResultMessage to the tasks exchange with routing key 'result'. On
failure, re-publish to the retry exchange while retryCount < MAX_RETRIES;
otherwise route the task to the DLX and publish a FAILURE ResultMessage. Acks
after processing (the aio-pika process() context manager handles the ack).
"""
import asyncio
import logging
from typing import Optional

import aio_pika
from aio_pika import IncomingMessage, Message, DeliveryMode
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractExchange

from . import config
from . import failure_flags
from . import scenarios
from .schemas import TaskMessage, ResultMessage
from .handlers import extract, vision, narrative

logger = logging.getLogger(__name__)

_connection: Optional[AbstractRobustConnection] = None


def _routing_key_for(task_type: str) -> str:
    """Map task type to its exchange routing key (text or vision)."""
    if task_type.upper() in ("EXTRACT", "NARRATIVE"):
        return config.RK_TEXT
    return config.RK_VISION


async def _publish(exchange: AbstractExchange, routing_key: str, body: bytes) -> None:
    """Publish a persistent message to the given exchange + routing key."""
    await exchange.publish(
        Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )


async def _publish_result(channel: AbstractChannel, result: ResultMessage) -> None:
    """Publish a ResultMessage to the tasks exchange with routing key 'result'."""
    tasks_exchange = await channel.get_exchange(config.EX_TASKS)
    await _publish(tasks_exchange, config.RK_RESULT, result.model_dump_json().encode())


async def _republish_retry(channel: AbstractChannel, task: TaskMessage) -> None:
    """Increment retryCount and re-publish to the TTL retry exchange."""
    task.retryCount += 1
    rk = _routing_key_for(task.taskType)
    retry_exchange = await channel.get_exchange(config.EX_RETRY)
    await _publish(retry_exchange, rk, task.model_dump_json().encode())
    logger.info(
        "Task %s re-published to retry exchange (retryCount=%d, rk=%s)",
        task.taskId,
        task.retryCount,
        rk,
    )


async def _publish_dlq(channel: AbstractChannel, task: TaskMessage) -> None:
    """Publish an exhausted task to the dead-letter exchange."""
    rk = _routing_key_for(task.taskType)
    dlx_exchange = await channel.get_exchange(config.EX_DLX)
    await _publish(dlx_exchange, rk, task.model_dump_json().encode())
    logger.warning(
        "Task %s exhausted retries (retryCount=%d) -> DLQ (rk=%s)",
        task.taskId,
        task.retryCount,
        rk,
    )


async def _dispatch(task: TaskMessage) -> dict:
    """Dispatch a task to the appropriate handler (handlers are synchronous).

    submissionId is passed to VISION and NARRATIVE handlers so they can look up
    failure flags recorded during EXTRACT (the text-carrying task).
    """
    task_type = task.taskType.upper()
    if task_type == "EXTRACT":
        return await asyncio.to_thread(extract.handle, task.payload)
    elif task_type == "VISION":
        return await asyncio.to_thread(vision.handle, task.payload, str(task.submissionId))
    elif task_type == "NARRATIVE":
        return await asyncio.to_thread(narrative.handle, task.payload, str(task.submissionId))
    raise ValueError(f"Unknown taskType: {task.taskType!r}")


async def _on_message(message: IncomingMessage, channel: AbstractChannel) -> None:
    """Process a single incoming task message. Acks after processing."""
    async with message.process(requeue=False):
        try:
            task = TaskMessage.model_validate_json(message.body)
        except Exception as exc:
            logger.error("Unparseable task message, dropping: %s", exc)
            return

        logger.info(
            "Received %s task %s (submissionId=%s, retryCount=%d)",
            task.taskType,
            task.taskId,
            task.submissionId,
            task.retryCount,
        )

        # On EXTRACT tasks the payload carries the full submission text, so we
        # can check failure-trigger keywords and record flags for this submission.
        # VISION/NARRATIVE tasks do not carry the text, so the registry bridges
        # the gap for those downstream handlers. (TEST-ONLY ephemeral memory.)
        if task.taskType.upper() == "EXTRACT":
            text = task.payload.get("submissionText", "") or ""
            failure_flags.record_flags(
                task.submissionId,
                fail_vision=scenarios.should_fail_vision(text),
                fail_narrative=scenarios.should_fail_narrative(text),
            )

        try:
            result_payload = await _dispatch(task)
            result = ResultMessage(
                taskId=task.taskId,
                submissionId=task.submissionId,
                taskType=task.taskType,
                status="SUCCESS",
                payload=result_payload,
                errorMessage=None,
            )
            await _publish_result(channel, result)
            logger.info("Task %s completed successfully", task.taskId)
        except Exception as exc:
            logger.error("Task %s failed: %s", task.taskId, exc)
            if task.retryCount < config.MAX_RETRIES:
                await _republish_retry(channel, task)
            else:
                failure_result = ResultMessage(
                    taskId=task.taskId,
                    submissionId=task.submissionId,
                    taskType=task.taskType,
                    status="FAILURE",
                    payload={},
                    errorMessage=str(exc),
                )
                await _publish_result(channel, failure_result)
                await _publish_dlq(channel, task)


async def connect() -> AbstractChannel:
    """Connect to RabbitMQ, open a channel with prefetch=1, and return it."""
    global _connection
    _connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
    channel = await _connection.channel()
    await channel.set_qos(prefetch_count=1)
    logger.info("RabbitMQ channel opened with prefetch_count=1")
    return channel


async def run() -> None:
    """Start the consumer loop on both task queues. Blocks until cancelled."""
    # Retry loop: backend declares the queues on startup; the worker may start
    # before the backend is ready, so we wait up to 30 s for the queues to appear.
    for attempt in range(10):
        try:
            channel = await connect()
            text_queue = await channel.declare_queue(config.Q_TASK_TEXT, durable=True, passive=True)
            vision_queue = await channel.declare_queue(config.Q_TASK_VISION, durable=True, passive=True)
            break
        except Exception as exc:
            logger.warning("Queue not ready yet (attempt %d/10): %s — retrying in 3s", attempt + 1, exc)
            await asyncio.sleep(3)
    else:
        logger.error("Queues never became available after 10 attempts — consumer not started")
        return

    await text_queue.consume(lambda msg: asyncio.ensure_future(_on_message(msg, channel)))
    await vision_queue.consume(lambda msg: asyncio.ensure_future(_on_message(msg, channel)))

    logger.info(
        "Mock consumer started — prefetch=1, listening on %s + %s",
        config.Q_TASK_TEXT,
        config.Q_TASK_VISION,
    )

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("Consumer shutting down")
        if _connection and not _connection.is_closed:
            await _connection.close()
        raise
