"""Deterministic COPE scenarios for E2E testing.

The mock extraction handler selects one of these fixtures based on keywords in
the submission text, so the deterministic Java rules engine produces
predictable Accept / Refer / Decline outcomes. Special keywords also trigger
failure and missing-field paths.
"""
from copy import deepcopy


# Clean, low-risk office — expected to Accept.
CLEAN_OFFICE_COPE = {
    "construction_type": "Fire Resistive",
    "construction_type_confidence": 0.95,
    "year_built": 2016,
    "year_built_confidence": 0.93,
    "roof_age": 2,
    "roof_age_confidence": 0.90,
    "occupancy_type": "Office",
    "occupancy_type_confidence": 0.94,
    "sprinklers": "Full NFPA-13",
    "sprinklers_confidence": 0.92,
    "alarm_type": "Central Station",
    "alarm_type_confidence": 0.91,
    "total_insured_value": 1000000,
    "total_insured_value_confidence": 0.96,
    "address": "100 Main St Springfield IL",
    "address_confidence": 0.88,
}

# Mid-risk warehouse — expected to Refer.
WAREHOUSE_COPE = {
    "construction_type": "Joisted Masonry",
    "construction_type_confidence": 0.90,
    "year_built": 1999,
    "year_built_confidence": 0.89,
    "roof_age": 12,
    "roof_age_confidence": 0.88,
    "occupancy_type": "Warehouse",
    "occupancy_type_confidence": 0.91,
    "sprinklers": "Partial",
    "sprinklers_confidence": 0.90,
    "alarm_type": "Central Station",
    "alarm_type_confidence": 0.89,
    "total_insured_value": 500000,
    "total_insured_value_confidence": 0.92,
    "address": "200 Industrial Blvd",
    "address_confidence": 0.88,
}

# High-risk coastal restaurant — expected to Decline.
COASTAL_RESTAURANT_COPE = {
    "construction_type": "Frame",
    "construction_type_confidence": 0.91,
    "year_built": 1969,
    "year_built_confidence": 0.90,
    "roof_age": 22,
    "roof_age_confidence": 0.89,
    "occupancy_type": "Restaurant",
    "occupancy_type_confidence": 0.90,
    "sprinklers": "None",
    "sprinklers_confidence": 0.91,
    "alarm_type": "Local",
    "alarm_type_confidence": 0.90,
    "total_insured_value": 2000000,
    "total_insured_value_confidence": 0.93,
    "address": "1 Ocean Drive Miami FL",
    "address_confidence": 0.88,
}


def get_cope_for_text(text: str) -> dict:
    """Select a COPE fixture based on keywords in the submission text."""
    upper = text.upper()
    if "COASTAL" in upper or "RESTAURANT" in upper:
        return deepcopy(COASTAL_RESTAURANT_COPE)
    if "WAREHOUSE" in upper:
        return deepcopy(WAREHOUSE_COPE)
    return deepcopy(CLEAN_OFFICE_COPE)


def should_fail_extract(text: str) -> bool:
    """True when the text requests a forced extraction failure."""
    return "FAIL EXTRACT" in text.upper()


def get_missing_tiv(text: str) -> bool:
    """True when the text requests a missing-TIV scenario."""
    return "MISSING TIV" in text.upper()
