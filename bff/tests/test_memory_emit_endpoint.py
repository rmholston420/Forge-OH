"""Tests for POST /api/memory/emit-consultation (Stage 5.6b).

Contract:
  * 503 when the memory surface is neither env-enabled nor port-composed.
  * 200 + normalized wire event when enabled via FORGE_MEMORY_EMIT_ENABLED=1
    (test path: no live DozerDB required).
  * 422 on missing / invalid body fields (runId min_length, resultCount ge=0).
  * Best-effort Socket.IO emit failure never breaks the endpoint.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.deps.memory_port import reset_memory_port
from bff.routers import memory as memory_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(memory_router.router, prefix="/api")
    return app


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    reset_memory_port(None)
    monkeypatch.delenv("FORGE_MEMORY_EMIT_ENABLED", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    yield
    reset_memory_port(None)


def test_emit_returns_503_when_disabled():
    client = TestClient(_make_app())
    r = client.post(
        "/api/memory/emit-consultation",
        json={
            "runId": "run-1",
            "tier": "semantic",
            "query": "hello",
            "resultCount": 0,
        },
    )
    assert r.status_code == 503
    assert "Memory emit disabled" in r.json()["detail"]


def test_emit_returns_wire_event_when_env_gate_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FORGE_MEMORY_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/memory/emit-consultation",
        json={
            "runId": "run-abc",
            "tier": "semantic",
            "query": "seeded triples",
            "resultCount": 2,
        },
    )
    assert r.status_code == 200
    wire = r.json()["data"]
    # Wire shape from event_normalize:
    #   {id, eventId, type, timestamp, source, summary, raw}
    # semantic fields live inside ``raw`` (kind/tier/query/result_count).
    assert wire["type"] == "memory_consultation"
    assert isinstance(wire["id"], str) and wire["id"]
    assert isinstance(wire["timestamp"], str) and wire["timestamp"]
    assert wire["summary"] == 'Memory consulted (semantic): "seeded triples" — 2 result(s)'
    raw = wire["raw"]
    assert raw["kind"] == "MemoryConsultationEvent"
    assert raw["tier"] == "semantic"
    assert raw["query"] == "seeded triples"
    assert raw["result_count"] == 2


def test_emit_422_when_run_id_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_MEMORY_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/memory/emit-consultation",
        json={
            "runId": "",
            "tier": "semantic",
            "query": "x",
            "resultCount": 0,
        },
    )
    assert r.status_code == 422


def test_emit_422_when_result_count_negative(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_MEMORY_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/memory/emit-consultation",
        json={
            "runId": "r",
            "tier": "semantic",
            "query": "x",
            "resultCount": -1,
        },
    )
    assert r.status_code == 422


def test_emit_422_when_field_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_MEMORY_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    r = client.post(
        "/api/memory/emit-consultation",
        json={"runId": "r", "tier": "semantic", "query": "x"},
    )
    assert r.status_code == 422


def test_emit_survives_socketio_failure(monkeypatch: pytest.MonkeyPatch):
    """The endpoint MUST still return 200 even if _emit blows up."""
    monkeypatch.setenv("FORGE_MEMORY_EMIT_ENABLED", "1")

    from bff.services import event_relay

    async def _boom(*_a, **_kw):
        raise RuntimeError("socketio down")

    monkeypatch.setattr(event_relay, "_emit", _boom, raising=False)

    client = TestClient(_make_app())
    r = client.post(
        "/api/memory/emit-consultation",
        json={
            "runId": "run-boom",
            "tier": "semantic",
            "query": "x",
            "resultCount": 0,
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["type"] == "memory_consultation"
