"""Unit tests for mock-ai-worker scenarios module.

Covers:
  - Fixture selection by keyword
  - All three failure-trigger helpers
  - Missing-TIV helper
"""
import pytest

from app import scenarios


class TestGetCopeForText:
    def test_restaurant_keyword_selects_coastal(self):
        cope = scenarios.get_cope_for_text("Full-service restaurant, Miami")
        assert cope["occupancy_type"] == "Restaurant"
        assert cope["construction_type"] == "Frame"

    def test_coastal_keyword_selects_coastal(self):
        cope = scenarios.get_cope_for_text("Coastal property near the sea")
        assert cope["occupancy_type"] == "Restaurant"

    def test_warehouse_keyword_selects_warehouse(self):
        cope = scenarios.get_cope_for_text("Suburban warehouse and distribution")
        assert cope["occupancy_type"] == "Warehouse"
        assert cope["construction_type"] == "Joisted Masonry"

    def test_default_selects_clean_office(self):
        cope = scenarios.get_cope_for_text("A commercial office building")
        assert cope["occupancy_type"] == "Office"
        assert cope["construction_type"] == "Fire Resistive"

    def test_case_insensitive_warehouse(self):
        cope = scenarios.get_cope_for_text("Large WAREHOUSE facility")
        assert cope["occupancy_type"] == "Warehouse"

    def test_deepcopy_returned(self):
        cope1 = scenarios.get_cope_for_text("office")
        cope2 = scenarios.get_cope_for_text("office")
        cope1["construction_type"] = "MUTATED"
        assert cope2["construction_type"] == "Fire Resistive"


class TestFailureTriggers:
    def test_should_fail_extract_positive(self):
        assert scenarios.should_fail_extract("FAIL EXTRACT Integration Test") is True

    def test_should_fail_extract_case_insensitive(self):
        assert scenarios.should_fail_extract("fail extract") is True

    def test_should_fail_extract_negative(self):
        assert scenarios.should_fail_extract("Normal office submission") is False

    def test_should_fail_vision_positive(self):
        assert scenarios.should_fail_vision("FAIL VISION test submission") is True

    def test_should_fail_vision_case_insensitive(self):
        assert scenarios.should_fail_vision("fail vision") is True

    def test_should_fail_vision_negative(self):
        assert scenarios.should_fail_vision("Office building, no failures") is False

    def test_should_fail_narrative_positive(self):
        assert scenarios.should_fail_narrative("FAIL NARRATIVE test") is True

    def test_should_fail_narrative_case_insensitive(self):
        assert scenarios.should_fail_narrative("fail narrative") is True

    def test_should_fail_narrative_negative(self):
        assert scenarios.should_fail_narrative("Normal warehouse text") is False

    def test_fail_vision_does_not_trigger_fail_extract(self):
        assert scenarios.should_fail_extract("FAIL VISION") is False

    def test_fail_narrative_does_not_trigger_fail_extract(self):
        assert scenarios.should_fail_extract("FAIL NARRATIVE") is False


class TestMissingTiv:
    def test_missing_tiv_positive(self):
        assert scenarios.get_missing_tiv("MISSING TIV scenario") is True

    def test_missing_tiv_case_insensitive(self):
        assert scenarios.get_missing_tiv("missing tiv") is True

    def test_missing_tiv_negative(self):
        assert scenarios.get_missing_tiv("Normal text with TIV: $1M") is False
