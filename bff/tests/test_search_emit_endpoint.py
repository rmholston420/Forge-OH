"""Tests for POST /api/search/emit (Stage 6.1).

Contract:
  * 503 when the search surface is neither env-enabled nor SearXNG-configured.
  * 200 + normalized wire event when enabled via FORGE_SEARCH_EMIT_ENABLED=1.
  * 200 + normalized wire event when enabled via FORGE_SEARXNG_BASE_URL.
  * 422 on missing / invalid body fields.
  * Best-effort Socket.IO emit failure never breaks the endpoint.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import search as search_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(search_router.router, prefix="/api")
    return app


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FORGE_SEARCH_EMIT_ENABLED", raising=False)
    monkeypatch.delenv("FORGE_SEARXNG_BASE_URL", raising=False)
    yield


def _valid_body() -> dict:
    return {
        "runId": "run-1",
        "query": "hello",
        "resultCount": 2,
        "provenance": "searxng:http://127.0.0.1:18888",
        "latencyMs": 42,
    }


def test_emit_returns_503_when_disabled():
    client = TestClient(_make_app())
    r = client.post("/api/search/emit", json=_valid_body())
    assert r.status_code == 503
    assert "Search emit disabled" in r.json()["detail"]


def test_emit_returns_wire_event_when_env_gate_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    r = client.post("/api/search/emit", json=_valid_body())
    assert r.status_code == 200
    wire = r.json()["data"]
    assert wire["type"] == "web_search"
    assert isinstance(wire["id"], str) and wire["id"]
    assert isinstance(wire["timestamp"], str) and wire["timestamp"]
    assert wire["summary"] == 'Web searched: "hello" — 2 result(s)'
    raw = wire["raw"]
    assert raw["kind"] == "WebSearchEvent"
    assert raw["query"] == "hello"
    assert raw["result_count"] == 2
    assert raw["provenance"] == "searxng:http://127.0.0.1:18888"
    assert raw["latency_ms"] == 42


def test_emit_returns_wire_event_when_searxng_base_url_set(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FORGE_SEARXNG_BASE_URL", "http://127.0.0.1:18888")
    client = TestClient(_make_app())
    r = client.post("/api/search/emit", json=_valid_body())
    assert r.status_code == 200
    assert r.json()["data"]["type"] == "web_search"


def test_emit_422_when_run_id_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    body = _valid_body()
    body["runId"] = ""
    r = client.post("/api/search/emit", json=body)
    assert r.status_code == 422


def test_emit_422_when_result_count_negative(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    body = _valid_body()
    body["resultCount"] = -1
    r = client.post("/api/search/emit", json=body)
    assert r.status_code == 422


def test_emit_422_when_latency_negative(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    body = _valid_body()
    body["latencyMs"] = -1
    r = client.post("/api/search/emit", json=body)
    assert r.status_code == 422


def test_emit_422_when_provenance_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    body = _valid_body()
    body["provenance"] = ""
    r = client.post("/api/search/emit", json=body)
    assert r.status_code == 422


def test_emit_422_when_field_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")
    client = TestClient(_make_app())
    body = _valid_body()
    body.pop("query")
    r = client.post("/api/search/emit", json=body)
    assert r.status_code == 422


def test_emit_survives_socketio_failure(monkeypatch: pytest.MonkeyPatch):
    """The endpoint MUST still return 200 even if _emit blows up."""
    monkeypatch.setenv("FORGE_SEARCH_EMIT_ENABLED", "1")

    from bff.services import event_relay

    async def _boom(*_a, **_kw):
        raise RuntimeError("socketio down")

    monkeypatch.setattr(event_relay, "_emit", _boom, raising=False)

    client = TestClient(_make_app())
    r = client.post("/api/search/emit", json=_valid_body())
    assert r.status_code == 200
    assert r.json()["data"]["type"] == "web_search"
