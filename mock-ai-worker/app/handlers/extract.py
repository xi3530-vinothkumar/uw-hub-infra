"""Mock extraction handler.

Returns a deterministic COPE fixture based on the submission text. Supports two
special keyword-driven paths for E2E testing: forced failure and missing-TIV.

The Java orchestrator expects the EXTRACT result payload to have:
  - Top-level fields for each COPE fact (string or number values)
  - A nested "confidences" dict mapping field_name -> float confidence (0.0-1.0)
  - A nested "source_snippets" dict mapping field_name -> verbatim snippet string
    (the substring of the submission text that supports the extracted value)

The scenarios module returns a flat dict with "_confidence" and "_snippet"
suffixed keys. This handler restructures that flat dict into the nested format
the Java backend expects, hoisting both suffix families into their respective
nested dicts while leaving all plain COPE fact keys at the top level.
"""
import logging

from .. import scenarios

logger = logging.getLogger(__name__)


def _restructure_cope(flat: dict) -> dict:
    """Split flat COPE dict into the nested format Java expects.

    Input:
        {
            "construction_type": "Fire Resistive",
            "construction_type_confidence": 0.95,
            "construction_type_snippet": "fire-resistive construction",
            ...
        }
    Output:
        {
            "construction_type": "Fire Resistive",
            ...,
            "confidences": {"construction_type": 0.95, ...},
            "source_snippets": {"construction_type": "fire-resistive construction", ...},
        }
    """
    facts: dict = {}
    confidences: dict = {}
    source_snippets: dict = {}

    for key, value in flat.items():
        if key.endswith("_confidence"):
            field_name = key[: -len("_confidence")]
            confidences[field_name] = float(value)
        elif key.endswith("_snippet"):
            field_name = key[: -len("_snippet")]
            source_snippets[field_name] = str(value)
        else:
            facts[key] = value

    facts["confidences"] = confidences
    facts["source_snippets"] = source_snippets
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
        cope_flat.pop("total_insured_value_snippet", None)
        logger.info("Mock extract: returning COPE without total_insured_value")

    result = _restructure_cope(cope_flat)
    logger.info(
        "Mock extract: returning %d facts, %d confidences, %d source_snippets",
        len(result) - 2,  # subtract confidences and source_snippets keys
        len(result.get("confidences", {})),
        len(result.get("source_snippets", {})),
    )
    return result
