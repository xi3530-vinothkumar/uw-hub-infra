"""Message envelope schemas — the contract with the Java orchestrator.

Mirrors the real ai-worker schemas and the Java TaskMessage / ResultMessage
models. Kept intentionally simple (str task types, str payload for tasks) to
match what the Java service publishes for E2E testing.
"""
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskMessage(BaseModel):
    taskId: UUID
    submissionId: UUID
    taskType: str
    payload: Dict[str, str]
    retryCount: int = 0


class ResultMessage(BaseModel):
    taskId: UUID
    submissionId: UUID
    taskType: str
    status: str                              # "SUCCESS" | "FAILURE"
    payload: Dict[str, Any] = Field(default_factory=dict)
    errorMessage: Optional[str] = None
