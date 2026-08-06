"""Tests for POST /api/_debug/inject-event (Stage 6.2).

Contract:
  * 404 (not 503, not 401) when FORGE_TIMELINE_DEBUG_INJECT is unset.
  * 200 + normalized wire event when the env flag is set.
  * The kind flows through _KIND_TO_TYPE. E.g. kind=Condensation ->
    type=condensation.
  * 422 on missing / empty required fields.
  * Extra fields on the raw event survive the round-trip (verifiable in
    the returned wire.raw dict).
  * Socket.IO emit failure never breaks the endpoint.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import debug as debug_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(debug_router.router, prefix="/api")
    return app


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FORGE_TIMELINE_DEBUG_INJECT", raising=False)
    yield


def test_returns_404_when_flag_unset():
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={"runId": "run-1", "kind": "Condensation", "extra": {}},
    )
    assert r.status_code == 404


def test_returns_wire_event_when_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={
            "runId": "run-1",
            "kind": "Condensation",
            "extra": {
                "forgotten_event_ids": ["a", "b", "c"],
                "summary": "Rolled up planning steps",
                "llm_response_id": "llm-1",
            },
        },
    )
    assert r.status_code == 200
    wire = r.json()["data"]
    assert wire["type"] == "condensation"
    assert "3 turns forgotten" in wire["summary"]
    assert wire["raw"]["forgotten_event_ids"] == ["a", "b", "c"]
    assert wire["raw"]["summary"] == "Rolled up planning steps"


def test_kind_condensation_request(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={"runId": "run-1", "kind": "CondensationRequest", "extra": {}},
    )
    assert r.status_code == 200
    wire = r.json()["data"]
    assert wire["type"] == "condensation_request"
    assert wire["summary"] == "Condensation requested"


def test_kind_condensation_summary_event(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={
            "runId": "run-1",
            "kind": "CondensationSummaryEvent",
            "extra": {"summary": "Prior 3 turns summarized here."},
        },
    )
    assert r.status_code == 200
    wire = r.json()["data"]
    assert wire["type"] == "condensation_summary"
    assert wire["summary"].startswith("Compression summary")


def test_422_on_empty_run_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={"runId": "", "kind": "Condensation", "extra": {}},
    )
    assert r.status_code == 422


def test_422_on_empty_kind(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={"runId": "run-1", "kind": "", "extra": {}},
    )
    assert r.status_code == 422


def test_extra_field_override_of_stamped_defaults(
    monkeypatch: pytest.MonkeyPatch,
):
    """Explicit id/timestamp/source in extra override the server-stamped values."""
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={
            "runId": "run-1",
            "kind": "Condensation",
            "extra": {
                "id": "fixed-id-123",
                "timestamp": "2020-01-01T00:00:00Z",
                "forgotten_event_ids": [],
            },
        },
    )
    assert r.status_code == 200
    wire = r.json()["data"]
    assert wire["id"] == "fixed-id-123"
    assert wire["timestamp"] == "2020-01-01T00:00:00Z"


def test_emit_failure_swallowed(monkeypatch: pytest.MonkeyPatch):
    """When event_relay._emit raises, the endpoint still returns 200."""
    import bff.services.event_relay as relay

    async def boom(*args, **kwargs):
        raise RuntimeError("no socket")

    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    monkeypatch.setattr(relay, "_emit", boom)
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={"runId": "run-1", "kind": "Condensation", "extra": {}},
    )
    assert r.status_code == 200
