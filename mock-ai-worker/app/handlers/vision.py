"""Mock vision handler — returns a fixed, deterministic photo assessment.

Supports the FAIL VISION keyword trigger: if the submission text (captured
during EXTRACT) contained "FAIL VISION", the failure_flags registry will have
recorded that flag for this submissionId, and this handler will raise so the
consumer routes the task through the retry topology and ultimately to the DLQ /
FAILED_AI status.
"""
from .. import failure_flags


def handle(payload: dict, submission_id: str = "") -> dict:
    """Produce a mock photo condition assessment.

    Raises ValueError if the FAIL VISION trigger is active for this submission.
    """
    if submission_id and failure_flags.should_fail_vision(submission_id):
        raise ValueError("Mock vision failure (FAIL VISION keyword present)")

    return {
        "photoId": payload.get("photoId", ""),
        "conditionScore": 30,
        "condition_score": 30,
        "summary": "Building in fair condition",
        "findings": ["Minor weathering"],
    }
