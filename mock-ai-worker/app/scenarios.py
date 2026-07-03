"""Deterministic COPE scenarios for E2E testing.

The mock extraction handler selects one of these fixtures based on keywords in
the submission text, so the deterministic Java rules engine produces
predictable Accept / Refer / Decline outcomes. Special keywords also trigger
failure and missing-field paths.

Each fixture contains three suffix families per COPE field:
  - plain key             e.g. "construction_type": "Fire Resistive"
  - _confidence suffix    e.g. "construction_type_confidence": 0.95
  - _snippet suffix       e.g. "construction_type_snippet": "fire-resistive construction"
                          A VERBATIM substring of the corresponding demo rawText.

Source rawText strings (canonical in demo/submissions/):
  accept_clean_office.json  — "Commercial office building at 123 Main St, Austin TX 78701.
                               12-story steel frame, fire-resistive construction. Built 2016.
                               Total insured value: $8,500,000. Fully sprinklered NFPA-13
                               system. Central station monitoring. New roof installed 2021.
                               Professional services occupancy (law firm). ..."
  refer_warehouse.json      — "Suburban warehouse and distribution center at 456 Industrial
                               Pkwy, Memphis TN 38103. Single story joisted masonry
                               construction, built 1999. TIV: $2,100,000. Partial sprinkler
                               system (rack storage only). Local alarm only. Roof last
                               replaced 2012. Warehouse/storage occupancy ..."
  decline_coastal_restaurant.json — "Coastal frame restaurant at 789 Beach Blvd, Miami FL
                               33139. Two-story wood frame construction built 1969. Total
                               insured value: $3,200,000. No sprinklers. Local fire alarm
                               only. Roof 22 years old showing wear. ..."
"""
from copy import deepcopy


# Clean, low-risk office — expected to Accept.
# Snippets are VERBATIM substrings from accept_clean_office.json rawText.
CLEAN_OFFICE_COPE = {
    "construction_type": "Fire Resistive",
    "construction_type_confidence": 0.95,
    "construction_type_snippet": "fire-resistive construction",
    "year_built": 2016,
    "year_built_confidence": 0.93,
    "year_built_snippet": "Built 2016",
    "roof_age": 2,
    "roof_age_confidence": 0.90,
    "roof_age_snippet": "New roof installed 2021",
    "occupancy_type": "Office",
    "occupancy_type_confidence": 0.94,
    "occupancy_type_snippet": "Professional services occupancy (law firm)",
    "sprinklers": "Full NFPA-13",
    "sprinklers_confidence": 0.92,
    "sprinklers_snippet": "Fully sprinklered NFPA-13 system",
    "alarm_type": "Central Station",
    "alarm_type_confidence": 0.91,
    "alarm_type_snippet": "Central station monitoring",
    "total_insured_value": 1000000,
    "total_insured_value_confidence": 0.96,
    "total_insured_value_snippet": "Total insured value: $8,500,000",
    "address": "100 Main St Springfield IL",
    "address_confidence": 0.88,
    "address_snippet": "123 Main St, Austin TX 78701",
}

# Mid-risk warehouse — expected to Refer.
# Snippets are VERBATIM substrings from refer_warehouse.json rawText.
WAREHOUSE_COPE = {
    "construction_type": "Joisted Masonry",
    "construction_type_confidence": 0.90,
    "construction_type_snippet": "joisted masonry construction",
    "year_built": 1999,
    "year_built_confidence": 0.89,
    "year_built_snippet": "built 1999",
    "roof_age": 12,
    "roof_age_confidence": 0.88,
    "roof_age_snippet": "Roof last replaced 2012",
    "occupancy_type": "Warehouse",
    "occupancy_type_confidence": 0.91,
    "occupancy_type_snippet": "Warehouse/storage occupancy",
    "sprinklers": "Partial",
    "sprinklers_confidence": 0.90,
    "sprinklers_snippet": "Partial sprinkler system (rack storage only)",
    "alarm_type": "Central Station",
    "alarm_type_confidence": 0.89,
    "alarm_type_snippet": "Local alarm only",
    "total_insured_value": 500000,
    "total_insured_value_confidence": 0.92,
    "total_insured_value_snippet": "TIV: $2,100,000",
    "address": "200 Industrial Blvd",
    "address_confidence": 0.88,
    "address_snippet": "456 Industrial Pkwy, Memphis TN 38103",
}

# High-risk coastal restaurant — expected to Decline.
# Snippets are VERBATIM substrings from decline_coastal_restaurant.json rawText.
COASTAL_RESTAURANT_COPE = {
    "construction_type": "Frame",
    "construction_type_confidence": 0.91,
    "construction_type_snippet": "Two-story wood frame construction",
    "year_built": 1969,
    "year_built_confidence": 0.90,
    "year_built_snippet": "built 1969",
    "roof_age": 22,
    "roof_age_confidence": 0.89,
    "roof_age_snippet": "Roof 22 years old showing wear",
    "occupancy_type": "Restaurant",
    "occupancy_type_confidence": 0.90,
    "occupancy_type_snippet": "Full-service restaurant with commercial kitchen",
    "sprinklers": "None",
    "sprinklers_confidence": 0.91,
    "sprinklers_snippet": "No sprinklers",
    "alarm_type": "Local",
    "alarm_type_confidence": 0.90,
    "alarm_type_snippet": "Local fire alarm only",
    "total_insured_value": 2000000,
    "total_insured_value_confidence": 0.93,
    "total_insured_value_snippet": "Total insured value: $3,200,000",
    "address": "1 Ocean Drive Miami FL",
    "address_confidence": 0.88,
    "address_snippet": "789 Beach Blvd, Miami FL 33139",
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


def should_fail_vision(text: str) -> bool:
    """True when the text requests a forced vision failure."""
    return "FAIL VISION" in text.upper()


def should_fail_narrative(text: str) -> bool:
    """True when the text requests a forced narrative failure."""
    return "FAIL NARRATIVE" in text.upper()


def get_missing_tiv(text: str) -> bool:
    """True when the text requests a missing-TIV scenario."""
    return "MISSING TIV" in text.upper()
