"""Mock AI worker configuration from environment.

This mock worker replaces the real ai-worker for E2E testing when Ollama is
unavailable. It is still stateless (no DB) and speaks the same RabbitMQ
contract as the real worker. Queue/exchange names MUST match the backend
RabbitTopologyConfig and the real worker's config.py.
"""
import os

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://uw:uwpass@localhost:5672/")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_REAL_LLM = os.getenv("USE_REAL_LLM", "false").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Queue/exchange names — MUST match backend RabbitTopologyConfig.
EX_TASKS, EX_RETRY, EX_DLX = "uw.tasks", "uw.retry", "uw.dlx"
RK_TEXT, RK_VISION, RK_RESULT = "text", "vision", "result"
Q_TASK_TEXT, Q_TASK_VISION = "queue.task.text", "queue.task.vision"
Q_RESULT = "queue.result"
