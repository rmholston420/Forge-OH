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


def test_synthetic_commit_sha_stamps_user_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-026 §Storage E2E affordance: injected user MessageEvents with
    ``extra.commit_sha_at_time_of_event`` get the sha stamped on the
    normalized wire event, exactly as the sha_lookup path would stamp
    a real ledger hit.  The Playwright restart-from-here spec depends
    on this branch to synthesize eligible events without touching the
    real event_commit_ledger.
    """
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    sha = "a" * 40
    r = client.post(
        "/api/_debug/inject-event",
        json={
            "runId": "run-1",
            "kind": "MessageEvent",
            "extra": {
                "source": "user",
                "llm_message": {"role": "user", "content": "hi"},
                "commit_sha_at_time_of_event": sha,
            },
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["type"] == "message"
    assert data["source"] == "user"
    assert data["commit_sha_at_time_of_event"] == sha
    # Guard against the sha leaking back into raw (it must be pop()ed).
    assert "commit_sha_at_time_of_event" not in data["raw"]


def test_synthetic_commit_sha_ignored_on_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-026 §Frontend contract: the sha stamp gate is
    ``kind==MessageEvent AND source==user``.  Even when a synthetic sha
    is supplied, an assistant-source message must NOT get the key
    (defends against the copy-paste failure where a test fixture
    accidentally makes assistant messages restart-eligible).
    """
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={
            "runId": "run-1",
            "kind": "MessageEvent",
            "extra": {
                "source": "agent",
                "llm_message": {"role": "assistant", "content": "hi"},
                "commit_sha_at_time_of_event": "a" * 40,
            },
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["source"] == "agent"
    assert "commit_sha_at_time_of_event" not in data


def test_no_sha_stamped_when_extra_omits_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backward-compat: injected events without ``commit_sha_at_time_of_event``
    behave exactly as before (no stamp).  This is the pre-ADR-026 shape
    the Stage 6.2 fork-from-here spec still relies on.
    """
    monkeypatch.setenv("FORGE_TIMELINE_DEBUG_INJECT", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/_debug/inject-event",
        json={
            "runId": "run-1",
            "kind": "MessageEvent",
            "extra": {
                "source": "user",
                "llm_message": {"role": "user", "content": "hi"},
            },
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["source"] == "user"
    assert "commit_sha_at_time_of_event" not in data
