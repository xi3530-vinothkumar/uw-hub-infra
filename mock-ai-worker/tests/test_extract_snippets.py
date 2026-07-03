"""Unit tests for mock-ai-worker extract handler — source_snippets coverage.

Verifies:
  - _restructure_cope correctly hoists _snippet keys into source_snippets dict
  - source_snippets are present and non-empty for all three scenario fixtures
  - Snippet values are verbatim strings (not modified)
  - Confidences are still correctly separated
  - source_snippets do not bleed into top-level COPE facts
"""
import pytest

from app.handlers.extract import _restructure_cope, handle
from app import scenarios


COPE_FIELDS = [
    "construction_type",
    "year_built",
    "roof_age",
    "occupancy_type",
    "sprinklers",
    "alarm_type",
    "total_insured_value",
    "address",
]


class TestRestructureCope:
    def test_splits_confidence_into_nested_dict(self):
        flat = {
            "construction_type": "Fire Resistive",
            "construction_type_confidence": 0.95,
            "construction_type_snippet": "fire-resistive construction",
        }
        result = _restructure_cope(flat)
        assert result["confidences"]["construction_type"] == 0.95
        assert "construction_type_confidence" not in result

    def test_splits_snippet_into_source_snippets(self):
        flat = {
            "construction_type": "Fire Resistive",
            "construction_type_confidence": 0.95,
            "construction_type_snippet": "fire-resistive construction",
        }
        result = _restructure_cope(flat)
        assert result["source_snippets"]["construction_type"] == "fire-resistive construction"
        assert "construction_type_snippet" not in result

    def test_plain_facts_remain_at_top_level(self):
        flat = {
            "construction_type": "Fire Resistive",
            "construction_type_confidence": 0.95,
            "construction_type_snippet": "fire-resistive construction",
            "year_built": 2016,
            "year_built_confidence": 0.93,
            "year_built_snippet": "Built 2016",
        }
        result = _restructure_cope(flat)
        assert result["construction_type"] == "Fire Resistive"
        assert result["year_built"] == 2016

    def test_source_snippets_key_always_present(self):
        flat = {"construction_type": "Frame", "construction_type_confidence": 0.90}
        result = _restructure_cope(flat)
        assert "source_snippets" in result
        assert isinstance(result["source_snippets"], dict)

    def test_confidences_key_always_present(self):
        flat = {"construction_type": "Frame"}
        result = _restructure_cope(flat)
        assert "confidences" in result
        assert isinstance(result["confidences"], dict)

    def test_no_suffix_keys_bleed_into_top_level(self):
        flat = {
            "addr": "100 Main",
            "addr_confidence": 0.88,
            "addr_snippet": "100 Main St",
        }
        result = _restructure_cope(flat)
        for key in result:
            assert not key.endswith("_confidence"), f"Unexpected key: {key}"
            assert not key.endswith("_snippet"), f"Unexpected key: {key}"


class TestExtractHandlerWithSnippets:
    """Integration-style tests on handle() — no RabbitMQ, no real LLM."""

    def _call_handle(self, text: str) -> dict:
        return handle({"submissionText": text})

    def test_office_result_has_source_snippets(self):
        result = self._call_handle("Commercial office building in Austin")
        assert "source_snippets" in result
        snippets = result["source_snippets"]
        assert isinstance(snippets, dict)
        assert len(snippets) > 0

    def test_office_snippet_for_every_cope_field(self):
        result = self._call_handle("Commercial office building in Austin")
        snippets = result["source_snippets"]
        for field in COPE_FIELDS:
            assert field in snippets, f"Missing snippet for field: {field}"
            assert isinstance(snippets[field], str)
            assert len(snippets[field]) > 0, f"Empty snippet for field: {field}"

    def test_warehouse_snippet_for_every_cope_field(self):
        result = self._call_handle("Suburban warehouse distribution center")
        snippets = result["source_snippets"]
        for field in COPE_FIELDS:
            assert field in snippets, f"Missing snippet for field: {field}"

    def test_coastal_restaurant_snippet_for_every_cope_field(self):
        result = self._call_handle("Coastal frame restaurant Miami FL")
        snippets = result["source_snippets"]
        for field in COPE_FIELDS:
            assert field in snippets, f"Missing snippet for field: {field}"

    def test_office_snippets_are_verbatim_from_source(self):
        """Spot-check key snippets against known substrings from accept_clean_office.json."""
        result = self._call_handle("Office building")
        snippets = result["source_snippets"]
        # These must be verbatim substrings from the demo rawText
        assert snippets["construction_type"] == "fire-resistive construction"
        assert snippets["sprinklers"] == "Fully sprinklered NFPA-13 system"
        assert snippets["alarm_type"] == "Central station monitoring"
        assert snippets["year_built"] == "Built 2016"
        assert snippets["roof_age"] == "New roof installed 2021"

    def test_warehouse_snippets_are_verbatim(self):
        result = self._call_handle("Warehouse facility Memphis")
        snippets = result["source_snippets"]
        assert snippets["construction_type"] == "joisted masonry construction"
        assert snippets["sprinklers"] == "Partial sprinkler system (rack storage only)"
        assert snippets["total_insured_value"] == "TIV: $2,100,000"

    def test_coastal_snippets_are_verbatim(self):
        result = self._call_handle("Coastal restaurant building")
        snippets = result["source_snippets"]
        assert snippets["construction_type"] == "Two-story wood frame construction"
        assert snippets["sprinklers"] == "No sprinklers"
        assert snippets["roof_age"] == "Roof 22 years old showing wear"

    def test_missing_tiv_removes_tiv_snippet(self):
        """When MISSING TIV is active, total_insured_value and its snippet are absent."""
        result = self._call_handle("Office building MISSING TIV scenario")
        assert "total_insured_value" not in result
        assert "total_insured_value" not in result.get("source_snippets", {})
        assert "total_insured_value" not in result.get("confidences", {})

    def test_confidences_still_correct_alongside_snippets(self):
        result = self._call_handle("Office building in Austin")
        confidences = result["confidences"]
        assert confidences["construction_type"] == 0.95
        assert confidences["year_built"] == 0.93

    def test_fail_extract_raises(self):
        with pytest.raises(ValueError, match="FAIL EXTRACT"):
            self._call_handle("FAIL EXTRACT trigger text")
