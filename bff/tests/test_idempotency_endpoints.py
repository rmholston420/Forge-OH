"""Stage 6.3 — /api/idempotency/{check,mark} endpoint tests.

Contract:
  * check on empty ledger returns completed=false, key set, cached=null.
  * mark then check returns completed=true, cached payload matches.
  * mark on already-present key returns recorded=false.
  * check + mark accept arbitrary tool_name / arguments (no allowlist).
  * missing required fields yield 422.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import idempotency as idempotency_router
from bff.services import idempotency_ledger


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fresh FastAPI app + initialised temp ledger + TestClient."""
    monkeypatch.setattr(
        idempotency_ledger, "DB_PATH", tmp_path / "endpoint-ledger.db"
    )
    app = FastAPI()
    app.include_router(idempotency_router.router, prefix="/api")
    asyncio.run(idempotency_ledger.init_db(app))
    try:
        with TestClient(app) as c:
            yield c
    finally:
        asyncio.run(idempotency_ledger.close_db(app))


# ---------------------------------------------------------------------------
# /check
# ---------------------------------------------------------------------------


class TestCheck:
    def test_returns_completed_false_on_empty_ledger(self, client: TestClient):
        r = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": "leaf-1",
                "tool_name": "write_note",
                "arguments": {"title": "hello"},
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["completed"] is False
        assert data["cached"] is None
        assert isinstance(data["key"], str) and len(data["key"]) == 64

    def test_returns_same_key_regardless_of_argument_order(
        self, client: TestClient
    ):
        r1 = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": "leaf-1",
                "tool_name": "write_note",
                "arguments": {"a": 1, "b": 2},
            },
        )
        r2 = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": "leaf-1",
                "tool_name": "write_note",
                "arguments": {"b": 2, "a": 1},
            },
        )
        assert r1.json()["data"]["key"] == r2.json()["data"]["key"]

    def test_null_leaf_accepted(self, client: TestClient):
        r = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": None,
                "tool_name": "write_note",
                "arguments": {},
            },
        )
        assert r.status_code == 200

    def test_missing_conversation_id_yields_422(self, client: TestClient):
        r = client.post(
            "/api/idempotency/check",
            json={"tool_name": "write_note", "arguments": {}},
        )
        assert r.status_code == 422

    def test_empty_conversation_id_yields_422(self, client: TestClient):
        r = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "",
                "tool_name": "write_note",
                "arguments": {},
            },
        )
        assert r.status_code == 422

    def test_missing_tool_name_yields_422(self, client: TestClient):
        r = client.post(
            "/api/idempotency/check",
            json={"conversation_id": "c", "arguments": {}},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /mark + /check round-trip
# ---------------------------------------------------------------------------


class TestMarkAndCheck:
    def test_mark_then_check_returns_completed_true(self, client: TestClient):
        payload = {
            "conversation_id": "conv-1",
            "leaf_event_id": "leaf-1",
            "tool_name": "write_note",
            "arguments": {"title": "a", "body": "b"},
            "result_summary": "wrote 1 byte",
            "result_json": {"path": "/tmp/a.txt", "bytes_written": 1},
        }
        rm = client.post("/api/idempotency/mark", json=payload)
        assert rm.status_code == 200
        mark_data = rm.json()["data"]
        assert mark_data["recorded"] is True
        assert isinstance(mark_data["key"], str)

        rc = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": "leaf-1",
                "tool_name": "write_note",
                "arguments": {"title": "a", "body": "b"},
            },
        )
        assert rc.status_code == 200
        check_data = rc.json()["data"]
        assert check_data["completed"] is True
        assert check_data["key"] == mark_data["key"]
        assert check_data["cached"] is not None
        assert check_data["cached"]["result_json"] == {
            "path": "/tmp/a.txt",
            "bytes_written": 1,
        }
        assert check_data["cached"]["result_summary"] == "wrote 1 byte"

    def test_second_mark_returns_recorded_false(self, client: TestClient):
        payload = {
            "conversation_id": "conv-1",
            "leaf_event_id": "leaf-1",
            "tool_name": "write_note",
            "arguments": {"title": "a"},
            "result_summary": "first",
            "result_json": {"attempt": 1},
        }
        first = client.post("/api/idempotency/mark", json=payload)
        assert first.status_code == 200
        assert first.json()["data"]["recorded"] is True

        # Second mark with same key.
        second_payload = dict(payload)
        second_payload["result_summary"] = "second"
        second_payload["result_json"] = {"attempt": 2}
        second = client.post("/api/idempotency/mark", json=second_payload)
        assert second.status_code == 200
        assert second.json()["data"]["recorded"] is False
        # First mark's payload wins per INSERT OR IGNORE.
        rc = client.post(
            "/api/idempotency/check",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": "leaf-1",
                "tool_name": "write_note",
                "arguments": {"title": "a"},
            },
        )
        assert rc.json()["data"]["cached"]["result_json"] == {"attempt": 1}

    def test_different_leaf_events_do_not_collide(self, client: TestClient):
        common = {
            "conversation_id": "conv-1",
            "tool_name": "write_note",
            "arguments": {"title": "a"},
            "result_summary": "ok",
        }
        client.post(
            "/api/idempotency/mark",
            json={**common, "leaf_event_id": "leaf-1", "result_json": {"x": 1}},
        )
        rc = client.post(
            "/api/idempotency/check",
            json={**common, "leaf_event_id": "leaf-2"},
        )
        assert rc.json()["data"]["completed"] is False

    def test_null_leaf_accepted_on_mark(self, client: TestClient):
        r = client.post(
            "/api/idempotency/mark",
            json={
                "conversation_id": "conv-1",
                "leaf_event_id": None,
                "tool_name": "write_note",
                "arguments": {"title": "a"},
                "result_summary": "ok",
                "result_json": {"ok": True},
            },
        )
        assert r.status_code == 200
        assert r.json()["data"]["recorded"] is True
