"""In-memory failure flag registry for the MOCK AI worker.

NOTE: This is TEST-ONLY ephemeral memory. It exists only in the mock worker
process and is intentionally not persisted, not shared across processes, and
not present in the real ai-worker. It enables E2E tests to trigger controlled
vision and narrative failures via keyword phrases in the submission text.

The EXTRACT handler records flags for a given submissionId when keywords
"FAIL VISION" or "FAIL NARRATIVE" appear in the submission text. Downstream
VISION and NARRATIVE handlers check these flags — since those task payloads do
not carry the full submission text, the registry bridges the gap.

Lifecycle: flags are set on EXTRACT and cleared never (process lifetime). A
fresh mock-worker process always starts with an empty registry, which is fine
for E2E test isolation (each test run starts a fresh pipeline).
"""
from __future__ import annotations

from uuid import UUID

# Registry: submissionId (str) -> {fail_vision: bool, fail_narrative: bool}
_registry: dict[str, dict[str, bool]] = {}


def record_flags(submission_id: str | UUID, fail_vision: bool, fail_narrative: bool) -> None:
    """Record failure flags for a submission (called from EXTRACT handler)."""
    key = str(submission_id)
    _registry[key] = {
        "fail_vision": fail_vision,
        "fail_narrative": fail_narrative,
    }


def get_flags(submission_id: str | UUID) -> dict[str, bool]:
    """Return the failure flags for a submission, defaulting to no failures."""
    return _registry.get(str(submission_id), {"fail_vision": False, "fail_narrative": False})


def should_fail_vision(submission_id: str | UUID) -> bool:
    """True if the FAIL VISION keyword was present in the submission text."""
    return get_flags(submission_id)["fail_vision"]


def should_fail_narrative(submission_id: str | UUID) -> bool:
    """True if the FAIL NARRATIVE keyword was present in the submission text."""
    return get_flags(submission_id)["fail_narrative"]
