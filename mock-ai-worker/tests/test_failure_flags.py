"""Unit tests for the failure_flags registry module.

Covers:
  - record_flags stores flags correctly
  - get_flags returns defaults for unknown submissionIds
  - should_fail_vision / should_fail_narrative helpers
  - UUID and string submissionId interoperability
  - Flags from one submission do not bleed into another
"""
import uuid

import pytest

from app import failure_flags


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the in-memory registry before every test for isolation."""
    failure_flags._registry.clear()
    yield
    failure_flags._registry.clear()


class TestRecordAndGet:
    def test_defaults_when_no_flags_recorded(self):
        sid = str(uuid.uuid4())
        flags = failure_flags.get_flags(sid)
        assert flags["fail_vision"] is False
        assert flags["fail_narrative"] is False

    def test_record_fail_vision(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=True, fail_narrative=False)
        assert failure_flags.get_flags(sid)["fail_vision"] is True
        assert failure_flags.get_flags(sid)["fail_narrative"] is False

    def test_record_fail_narrative(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=True)
        assert failure_flags.get_flags(sid)["fail_vision"] is False
        assert failure_flags.get_flags(sid)["fail_narrative"] is True

    def test_record_both_flags(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=True, fail_narrative=True)
        flags = failure_flags.get_flags(sid)
        assert flags["fail_vision"] is True
        assert flags["fail_narrative"] is True

    def test_uuid_object_as_submission_id(self):
        sid = uuid.uuid4()
        failure_flags.record_flags(sid, fail_vision=True, fail_narrative=False)
        # Retrieve with string form — must match
        assert failure_flags.should_fail_vision(str(sid)) is True

    def test_flags_do_not_bleed_across_submissions(self):
        sid1 = str(uuid.uuid4())
        sid2 = str(uuid.uuid4())
        failure_flags.record_flags(sid1, fail_vision=True, fail_narrative=True)
        failure_flags.record_flags(sid2, fail_vision=False, fail_narrative=False)
        assert failure_flags.should_fail_vision(sid2) is False
        assert failure_flags.should_fail_narrative(sid2) is False


class TestHelpers:
    def test_should_fail_vision_true(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=True, fail_narrative=False)
        assert failure_flags.should_fail_vision(sid) is True

    def test_should_fail_vision_false(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=False)
        assert failure_flags.should_fail_vision(sid) is False

    def test_should_fail_narrative_true(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=True)
        assert failure_flags.should_fail_narrative(sid) is True

    def test_should_fail_narrative_false(self):
        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=False)
        assert failure_flags.should_fail_narrative(sid) is False

    def test_unknown_id_returns_false_for_vision(self):
        assert failure_flags.should_fail_vision(str(uuid.uuid4())) is False

    def test_unknown_id_returns_false_for_narrative(self):
        assert failure_flags.should_fail_narrative(str(uuid.uuid4())) is False


class TestVisionHandlerIntegration:
    """Verify vision.handle() raises when FAIL VISION flag is set."""

    def test_vision_raises_when_flag_set(self):
        from app.handlers.vision import handle

        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=True, fail_narrative=False)
        with pytest.raises(ValueError, match="FAIL VISION"):
            handle({"photoId": "p1", "imageBase64": ""}, sid)

    def test_vision_succeeds_when_flag_not_set(self):
        from app.handlers.vision import handle

        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=False)
        result = handle({"photoId": "p1", "imageBase64": ""}, sid)
        assert result["photoId"] == "p1"
        assert "conditionScore" in result

    def test_vision_succeeds_with_no_submission_id(self):
        from app.handlers.vision import handle

        result = handle({"photoId": "p2", "imageBase64": ""})
        assert result["photoId"] == "p2"


class TestNarrativeHandlerIntegration:
    """Verify narrative.handle() raises when FAIL NARRATIVE flag is set."""

    def test_narrative_raises_when_flag_set(self):
        from app.handlers.narrative import handle

        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=True)
        with pytest.raises(ValueError, match="FAIL NARRATIVE"):
            handle({"compositeScore": 45, "recommendation": "REFER"}, sid)

    def test_narrative_succeeds_when_flag_not_set(self):
        from app.handlers.narrative import handle

        sid = str(uuid.uuid4())
        failure_flags.record_flags(sid, fail_vision=False, fail_narrative=False)
        result = handle({"compositeScore": 45, "recommendation": "REFER"}, sid)
        assert "narrative" in result
        assert "pricing_guidance" in result

    def test_narrative_succeeds_with_no_submission_id(self):
        from app.handlers.narrative import handle

        result = handle({"compositeScore": 20, "recommendation": "Accept"})
        assert "narrative" in result
