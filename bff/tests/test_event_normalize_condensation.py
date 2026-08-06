"""Tests for the Stage 6.2 condensation-family normalizer branches.

Kept separate from ``test_event_normalize.py`` (Stage 3.1 security risk
suite) so the new coverage can be run in isolation:

    pytest bff/tests/test_event_normalize_condensation.py -q

Covers the three SDK v1.40.0 kinds normalize_event now recognizes:
  * ``Condensation``            -> type ``"condensation"``
  * ``CondensationRequest``     -> type ``"condensation_request"``
  * ``CondensationSummaryEvent``-> type ``"condensation_summary"``

Field shapes verified live against SDK v1.40.0 on Colossus 2026-08-06 EDT:
  * ``Condensation``: forgotten_event_ids (set), summary (str|None),
    summary_offset (int|None), llm_response_id (str).
  * ``CondensationRequest``: no informative payload.
  * ``CondensationSummaryEvent``: only ``summary`` (str).
"""

from bff.services.event_normalize import normalize_event


# ---------------------------------------------------------------------------
# Condensation
# ---------------------------------------------------------------------------


class TestCondensation:
    def _raw(self, **extra):
        base = {
            "id": "c1",
            "kind": "Condensation",
            "timestamp": "2026-08-06T05:00:00Z",
            "source": "environment",
            "forgotten_event_ids": ["e1", "e2", "e3"],
            "summary": None,
            "summary_offset": None,
            "llm_response_id": "llm-1",
        }
        base.update(extra)
        return base

    def test_type_is_condensation(self):
        out = normalize_event(self._raw())
        assert out["type"] == "condensation"

    def test_summary_reports_forgotten_count(self):
        out = normalize_event(self._raw())
        assert "3 turns forgotten" in out["summary"]

    def test_singular_one_turn(self):
        out = normalize_event(self._raw(forgotten_event_ids=["only"]))
        assert "1 turn forgotten" in out["summary"]
        assert "1 turns" not in out["summary"]

    def test_empty_forgotten_still_renders(self):
        out = normalize_event(self._raw(forgotten_event_ids=[]))
        assert "0 turns forgotten" in out["summary"]

    def test_summary_text_appended_when_present(self):
        out = normalize_event(self._raw(summary="Rolled up 3 planning steps."))
        # Base line + summary text
        assert "3 turns forgotten" in out["summary"]
        assert "Rolled up 3 planning steps." in out["summary"]

    def test_long_summary_elided(self):
        long_text = "x" * 300
        out = normalize_event(self._raw(summary=long_text))
        # Elision marker present; total length reasonable
        assert "…" in out["summary"]
        assert len(out["summary"]) < 300

    def test_missing_forgotten_defaults_to_zero(self):
        raw = self._raw()
        raw.pop("forgotten_event_ids")
        out = normalize_event(raw)
        assert "0 turns forgotten" in out["summary"]

    def test_raw_preserved(self):
        out = normalize_event(self._raw(summary="hi"))
        assert out["raw"]["kind"] == "Condensation"
        assert out["raw"]["llm_response_id"] == "llm-1"


# ---------------------------------------------------------------------------
# CondensationRequest
# ---------------------------------------------------------------------------


class TestCondensationRequest:
    def _raw(self, **extra):
        base = {
            "id": "cr1",
            "kind": "CondensationRequest",
            "timestamp": "2026-08-06T05:00:01Z",
            "source": "environment",
        }
        base.update(extra)
        return base

    def test_type_is_condensation_request(self):
        out = normalize_event(self._raw())
        assert out["type"] == "condensation_request"

    def test_summary_is_static_marker(self):
        out = normalize_event(self._raw())
        assert out["summary"] == "Condensation requested"


# ---------------------------------------------------------------------------
# CondensationSummaryEvent
# ---------------------------------------------------------------------------


class TestCondensationSummaryEvent:
    def _raw(self, **extra):
        base = {
            "id": "cs1",
            "kind": "CondensationSummaryEvent",
            "timestamp": "2026-08-06T05:00:02Z",
            "source": "environment",
            "summary": "Summary of 3 forgotten turns.",
        }
        base.update(extra)
        return base

    def test_type_is_condensation_summary(self):
        out = normalize_event(self._raw())
        assert out["type"] == "condensation_summary"

    def test_summary_prefixed(self):
        out = normalize_event(self._raw())
        assert out["summary"].startswith("Compression summary")
        assert "Summary of 3 forgotten turns." in out["summary"]

    def test_empty_summary_fallback(self):
        out = normalize_event(self._raw(summary=""))
        assert out["summary"] == "Compression summary"

    def test_missing_summary_field_fallback(self):
        raw = self._raw()
        raw.pop("summary")
        out = normalize_event(raw)
        assert out["summary"] == "Compression summary"

    def test_long_summary_elided(self):
        out = normalize_event(self._raw(summary="y" * 300))
        assert "…" in out["summary"]


# ---------------------------------------------------------------------------
# Regression: existing status-mapped kinds untouched
# ---------------------------------------------------------------------------


class TestExistingKindsUntouched:
    def test_conversation_state_update_still_status(self):
        out = normalize_event({
            "id": "s1",
            "kind": "ConversationStateUpdateEvent",
            "timestamp": "2026-08-06T05:00:03Z",
            "source": "agent",
        })
        assert out["type"] == "status"

    def test_llm_completion_log_still_status(self):
        out = normalize_event({
            "id": "s2",
            "kind": "LLMCompletionLogEvent",
            "timestamp": "2026-08-06T05:00:04Z",
            "source": "agent",
        })
        assert out["type"] == "status"
