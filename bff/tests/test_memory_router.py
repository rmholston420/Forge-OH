"""Tests for bff/routers/memory.py (Stage 5.6a / ADR-024).

Exercises the /api/memory/recent-writes endpoint against:
  1. A missing MemoryPort (dev boot without NEO4J_PASSWORD) -> 503.
  2. A composed MemoryPort backed by the in-memory DozerDbMemoryAdapter -> 200
     with the correct wire shape and newest-first ordering.

Uses ``bff.deps.memory_port.reset_memory_port`` to inject the test adapter
so no live infra is required.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.deps.memory_port import reset_memory_port
from bff.routers import memory as memory_router
from openhands_tools_ext.memory.adapters.dozerdb.adapter import (
    DozerDbMemoryAdapter,
    InMemoryGraphBackend,
    InMemoryTemporalIndex,
    NoOpAmgPolicy,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(memory_router.router, prefix="/api")
    return app


def _run(coro):
    """Run a coroutine to completion in a fresh event loop.

    Python 3.14 removed the implicit ``asyncio.get_event_loop()`` fallback
    in non-async contexts; sync test bodies must create their own loop.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_memory_port(None)
    yield
    reset_memory_port(None)


def test_recent_writes_returns_503_when_port_unavailable(monkeypatch):
    # Ensure the get_memory_port() lazy path can't compose either.
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    client = TestClient(_make_app())
    r = client.get("/api/memory/recent-writes")
    assert r.status_code == 503
    body = r.json()
    assert "Memory service unavailable" in body["detail"]


def test_recent_writes_returns_empty_list_when_port_has_no_writes():
    adapter = DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
    )
    reset_memory_port(adapter)
    try:
        client = TestClient(_make_app())
        r = client.get("/api/memory/recent-writes")
        assert r.status_code == 200
        assert r.json() == {"data": []}
    finally:
        reset_memory_port(None)
        _run(adapter.close())


def test_recent_writes_projects_write_to_wire_shape():
    adapter = DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
    )
    _run(
        adapter.write_event(
            "colossus", "runs", "dozerdb",
            provenance="agent",
            confidence=0.9,
            source_citation="build log",
            pii_tier="Public",
        )
    )
    reset_memory_port(adapter)
    try:
        client = TestClient(_make_app())
        r = client.get("/api/memory/recent-writes")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body and isinstance(body["data"], list)
        assert len(body["data"]) == 1
        row = body["data"][0]
        assert row["subject"] == "colossus"
        assert row["predicate"] == "runs"
        assert row["object"] == "dozerdb"
        assert row["provenance"] == "agent"
        assert row["confidence"] == 0.9
        assert row["piiTier"] == "Public"
        assert row["sourceCitation"] == "build log"
        assert isinstance(row["writtenAt"], str)
        assert isinstance(row["id"], str) and len(row["id"]) > 0
    finally:
        reset_memory_port(None)
        _run(adapter.close())


def test_recent_writes_respects_limit_query_param():
    adapter = DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
    )
    async def _seed():
        for i in range(4):
            await adapter.write_event(
                f"s{i}", "p", "o", provenance="agent", confidence=0.5
            )
            await asyncio.sleep(0.001)

    _run(_seed())
    reset_memory_port(adapter)
    try:
        client = TestClient(_make_app())
        r = client.get("/api/memory/recent-writes?limit=2")
        assert r.status_code == 200
        rows = r.json()["data"]
        assert len(rows) == 2
        # newest-first
        assert rows[0]["subject"] == "s3"
        assert rows[1]["subject"] == "s2"
    finally:
        reset_memory_port(None)
        _run(adapter.close())


def test_recent_writes_rejects_out_of_range_limit():
    adapter = DozerDbMemoryAdapter(
        graph=InMemoryGraphBackend(),
        amg=NoOpAmgPolicy(),
        temporal=InMemoryTemporalIndex(),
    )
    reset_memory_port(adapter)
    try:
        client = TestClient(_make_app())
        r = client.get("/api/memory/recent-writes?limit=0")
        assert r.status_code == 422
        r = client.get("/api/memory/recent-writes?limit=201")
        assert r.status_code == 422
    finally:
        reset_memory_port(None)
        _run(adapter.close())
