"""Tests for bff/services/memory_events.py (Stage 5.6a / ADR-024).

Covers the pure factory (``build_memory_consultation_event``) and the
emit wrapper (``emit_memory_consultation``). The wrapper is exercised
with the Socket.IO server left un-set, so the emit-side effect is a
no-op and we assert on the returned normalized wire event instead.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from bff.services.event_normalize import normalize_event
from bff.services.memory_events import (
    MEMORY_CONSULTATION_KIND,
    build_memory_consultation_event,
    emit_memory_consultation,
)


class TestBuildMemoryConsultationEvent:
    def test_returns_dict_with_kind_field(self):
        ev = build_memory_consultation_event(
            conversation_id="cid-1",
            tier="semantic",
            query="how does dozerdb write events",
            result_count=3,
        )
        assert ev["kind"] == MEMORY_CONSULTATION_KIND
        assert ev["kind"] == "MemoryConsultationEvent"

    def test_carries_tier_query_result_count(self):
        ev = build_memory_consultation_event(
            conversation_id="cid-1",
            tier="semantic",
            query="q",
            result_count=5,
        )
        assert ev["tier"] == "semantic"
        assert ev["query"] == "q"
        assert ev["result_count"] == 5

    def test_generates_uuid_when_no_event_id(self):
        ev = build_memory_consultation_event(
            conversation_id="cid",
            tier="t",
            query="q",
            result_count=0,
        )
        assert isinstance(ev["id"], str) and len(ev["id"]) > 0

    def test_accepts_explicit_event_id(self):
        ev = build_memory_consultation_event(
            conversation_id="cid",
            tier="t",
            query="q",
            result_count=0,
            event_id="fixed-id",
        )
        assert ev["id"] == "fixed-id"

    def test_defaults_timestamp_to_now_utc_iso(self):
        ev = build_memory_consultation_event(
            conversation_id="cid",
            tier="t",
            query="q",
            result_count=0,
        )
        parsed = datetime.fromisoformat(ev["timestamp"])
        assert parsed.tzinfo is not None

    def test_accepts_explicit_timestamp(self):
        ts = datetime(2026, 8, 6, 3, 0, 0, tzinfo=timezone.utc)
        ev = build_memory_consultation_event(
            conversation_id="cid",
            tier="t",
            query="q",
            result_count=0,
            timestamp=ts,
        )
        assert ev["timestamp"] == ts.isoformat()

    def test_tags_run_id_from_conversation_id(self):
        ev = build_memory_consultation_event(
            conversation_id="cid-42",
            tier="t",
            query="q",
            result_count=0,
        )
        assert ev["runId"] == "cid-42"

    def test_rejects_empty_conversation_id(self):
        with pytest.raises(ValueError, match="conversation_id"):
            build_memory_consultation_event(
                conversation_id="",
                tier="t",
                query="q",
                result_count=0,
            )

    def test_rejects_empty_tier(self):
        with pytest.raises(ValueError, match="tier"):
            build_memory_consultation_event(
                conversation_id="cid",
                tier="",
                query="q",
                result_count=0,
            )

    def test_rejects_non_string_query(self):
        with pytest.raises(ValueError, match="query"):
            build_memory_consultation_event(
                conversation_id="cid",
                tier="t",
                query=None,  # type: ignore[arg-type]
                result_count=0,
            )

    def test_rejects_bool_result_count(self):
        # bool is a subclass of int in Python; catch it explicitly.
        with pytest.raises(ValueError, match="result_count"):
            build_memory_consultation_event(
                conversation_id="cid",
                tier="t",
                query="q",
                result_count=True,  # type: ignore[arg-type]
            )

    def test_rejects_negative_result_count(self):
        with pytest.raises(ValueError, match="result_count"):
            build_memory_consultation_event(
                conversation_id="cid",
                tier="t",
                query="q",
                result_count=-1,
            )


class TestNormalizeMemoryConsultation:
    def test_projects_kind_to_memory_consultation_type(self):
        raw = build_memory_consultation_event(
            conversation_id="cid",
            tier="semantic",
            query="colossus",
            result_count=2,
        )
        wire = normalize_event(raw)
        assert wire["type"] == "memory_consultation"

    def test_summary_shape(self):
        raw = build_memory_consultation_event(
            conversation_id="cid",
            tier="semantic",
            query="colossus",
            result_count=2,
        )
        wire = normalize_event(raw)
        assert wire["summary"] == 'Memory consulted (semantic): "colossus" — 2 result(s)'

    def test_summary_falls_back_when_query_missing(self):
        # Simulate a partial event to prove the summary is defensive.
        raw = {
            "id": "e1",
            "kind": "MemoryConsultationEvent",
            "timestamp": "2026-08-06T03:00:00+00:00",
            "tier": "semantic",
            # no query, no result_count
        }
        wire = normalize_event(raw)
        assert wire["type"] == "memory_consultation"
        assert "(query)" in wire["summary"]
        assert "—" in wire["summary"]

    def test_explicit_summary_overrides_default_render(self):
        raw = build_memory_consultation_event(
            conversation_id="cid",
            tier="semantic",
            query="q",
            result_count=1,
        )
        raw["summary"] = "custom"
        wire = normalize_event(raw)
        assert wire["summary"] == "custom"


class TestEmitMemoryConsultation:
    def test_returns_wire_event_when_sio_unset(self):
        # bff.services.event_relay._sio is None at import time in tests.
        # emit should still produce and return the wire event without raising.
        loop = asyncio.new_event_loop()
        try:
            wire = loop.run_until_complete(
                emit_memory_consultation(
                    conversation_id="cid",
                    tier="semantic",
                    query="q",
                    result_count=1,
                )
            )
        finally:
            loop.close()
        assert wire["type"] == "memory_consultation"
        assert wire["source"] == "memory"
        assert wire["raw"]["tier"] == "semantic"
