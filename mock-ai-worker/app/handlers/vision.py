"""Mock vision handler — returns a fixed, deterministic photo assessment."""


def handle(payload: dict) -> dict:
    """Produce a mock photo condition assessment."""
    return {
        "photoId": payload.get("photoId", ""),
        "conditionScore": 30,
        "condition_score": 30,
        "summary": "Building in fair condition",
        "findings": ["Minor weathering"],
    }
