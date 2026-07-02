"""Mock extraction handler.

Returns a deterministic COPE fixture based on the submission text. Supports two
special keyword-driven paths for E2E testing: forced failure and missing-TIV.

The Java orchestrator expects the EXTRACT result payload to have:
  - Top-level fields for each COPE fact (string or number values)
  - A nested "confidences" dict mapping field_name -> float confidence (0.0-1.0)
  - An optional nested "source_snippets" dict mapping field_name -> snippet string

The scenarios module returns a flat dict with "_confidence" suffixed keys. This
handler restructures that into the nested format the Java backend expects.
"""
import logging

from .. import scenarios

logger = logging.getLogger(__name__)


def _restructure_cope(flat: dict) -> dict:
    """Split flat COPE dict (with _confidence suffixes) into the nested format.

    Input:  {"construction_type": "Fire Resistive", "construction_type_confidence": 0.95, ...}
    Output: {"construction_type": "Fire Resistive", ..., "confidences": {"construction_type": 0.95, ...}}
    """
    facts: dict = {}
    confidences: dict = {}

    for key, value in flat.items():
        if key.endswith("_confidence"):
            field_name = key[: -len("_confidence")]
            confidences[field_name] = float(value)
        else:
            facts[key] = value

    facts["confidences"] = confidences
    return facts


def handle(payload: dict) -> dict:
    """Produce a mock COPE profile from the submission text."""
    text = payload.get("submissionText", "") or ""

    if scenarios.should_fail_extract(text):
        raise ValueError("Mock extraction failure (FAIL EXTRACT keyword present)")

    cope_flat = scenarios.get_cope_for_text(text)

    if scenarios.get_missing_tiv(text):
        cope_flat.pop("total_insured_value", None)
        cope_flat.pop("total_insured_value_confidence", None)
        logger.info("Mock extract: returning COPE without total_insured_value")

    result = _restructure_cope(cope_flat)
    logger.info("Mock extract: returning %d facts, %d confidences",
                len(result) - 1, len(result.get("confidences", {})))
    return result
