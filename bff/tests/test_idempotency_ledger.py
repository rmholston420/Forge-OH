"""Stage 6.3 — idempotency ledger unit tests.

Covers the pure SQLite service in bff/services/idempotency_ledger.py:
  * init_db / close_db lifecycle
  * key stability (order-independent argument dict)
  * has_completed / mark_completed roundtrip
  * INSERT OR IGNORE on duplicate mark
  * get_cached_result with and without result_json
  * clear_conversation scope
  * "root" sentinel for leaf_event_id=None

Uses a temp-directory DB per test to keep the on-disk ledger isolated.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Callable

import pytest
from fastapi import FastAPI

from bff.services import idempotency_ledger


@pytest.fixture
def temp_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install a temp DB_PATH and yield an initialised FastAPI app.

    The ledger module reads ``DB_PATH`` at ``init_db`` time; we patch the
    module-level attribute so the on-disk file lives under tmp_path.
    """
    db_path = tmp_path / "ledger.db"
    monkeypatch.setattr(idempotency_ledger, "DB_PATH", db_path)
    app = FastAPI()
    asyncio.run(idempotency_ledger.init_db(app))
    try:
        yield app
    finally:
        asyncio.run(idempotency_ledger.close_db(app))


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


class TestKeyDerivation:
    def test_key_is_sha256_hex(self):
        key = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "a", "body": "b"}
        )
        assert len(key) == 64
        int(key, 16)  # raises if not hex

    def test_argument_dict_order_does_not_affect_key(self):
        k1 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "a", "body": "b"}
        )
        k2 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"body": "b", "title": "a"}
        )
        assert k1 == k2

    def test_different_conversation_yields_different_key(self):
        k1 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "a"}
        )
        k2 = idempotency_ledger.compute_idempotency_key(
            "conv-2", "leaf-1", "write_note", {"title": "a"}
        )
        assert k1 != k2

    def test_different_leaf_yields_different_key(self):
        k1 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "a"}
        )
        k2 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-2", "write_note", {"title": "a"}
        )
        assert k1 != k2

    def test_different_tool_yields_different_key(self):
        k1 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "a"}
        )
        k2 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "delete_file", {"title": "a"}
        )
        assert k1 != k2

    def test_different_arguments_yields_different_key(self):
        k1 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "a"}
        )
        k2 = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "b"}
        )
        assert k1 != k2

    def test_none_leaf_maps_to_root_sentinel(self):
        k_none = idempotency_ledger.compute_idempotency_key(
            "conv-1", None, "write_note", {"title": "a"}
        )
        k_root = idempotency_ledger.compute_idempotency_key(
            "conv-1", "root", "write_note", {"title": "a"}
        )
        assert k_none == k_root

    def test_empty_leaf_string_falsy_maps_to_root(self):
        k_empty = idempotency_ledger.compute_idempotency_key(
            "conv-1", "", "write_note", {"title": "a"}
        )
        k_root = idempotency_ledger.compute_idempotency_key(
            "conv-1", "root", "write_note", {"title": "a"}
        )
        assert k_empty == k_root


# ---------------------------------------------------------------------------
# Ledger CRUD
# ---------------------------------------------------------------------------


class TestLedgerCRUD:
    def test_has_completed_false_on_empty_ledger(self, temp_ledger: FastAPI):
        result = asyncio.run(
            idempotency_ledger.has_completed(temp_ledger, "nonexistent-key")
        )
        assert result is False

    def test_mark_then_has_completed_returns_true(self, temp_ledger: FastAPI):
        key = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "hello"}
        )
        asyncio.run(
            idempotency_ledger.mark_completed(
                temp_ledger,
                key=key,
                conversation_id="conv-1",
                leaf_event_id="leaf-1",
                tool_name="write_note",
                arguments={"title": "hello"},
                result_summary="wrote 5 bytes",
                result_json={"path": "/tmp/x.txt", "bytes_written": 5},
            )
        )
        assert asyncio.run(idempotency_ledger.has_completed(temp_ledger, key))

    def test_get_cached_result_returns_payload(self, temp_ledger: FastAPI):
        key = "test-key"
        asyncio.run(
            idempotency_ledger.mark_completed(
                temp_ledger,
                key=key,
                conversation_id="conv-1",
                leaf_event_id="leaf-1",
                tool_name="write_note",
                arguments={"title": "a"},
                result_summary="ok",
                result_json={"path": "/tmp/x.txt"},
            )
        )
        cached = asyncio.run(idempotency_ledger.get_cached_result(temp_ledger, key))
        assert cached is not None
        assert cached["result_summary"] == "ok"
        assert cached["result_json"] == {"path": "/tmp/x.txt"}
        assert cached["completed_at"] > 0

    def test_get_cached_result_none_for_missing_key(self, temp_ledger: FastAPI):
        cached = asyncio.run(
            idempotency_ledger.get_cached_result(temp_ledger, "no-such-key")
        )
        assert cached is None

    def test_get_cached_result_with_null_result_json(self, temp_ledger: FastAPI):
        key = "no-payload-key"
        asyncio.run(
            idempotency_ledger.mark_completed(
                temp_ledger,
                key=key,
                conversation_id="conv-1",
                leaf_event_id="leaf-1",
                tool_name="notify",
                arguments={},
                result_summary="sent",
                result_json=None,
            )
        )
        cached = asyncio.run(idempotency_ledger.get_cached_result(temp_ledger, key))
        assert cached is not None
        assert cached["result_summary"] == "sent"
        assert cached["result_json"] is None

    def test_duplicate_mark_is_noop(self, temp_ledger: FastAPI):
        key = "dupe-key"

        async def run() -> None:
            for i in range(2):
                await idempotency_ledger.mark_completed(
                    temp_ledger,
                    key=key,
                    conversation_id="conv-1",
                    leaf_event_id="leaf-1",
                    tool_name="write_note",
                    arguments={"title": "x"},
                    result_summary=f"attempt-{i}",
                    result_json={"i": i},
                )

        asyncio.run(run())
        # The first insert wins per INSERT OR IGNORE — the second attempt
        # neither raises nor overwrites the summary.
        cached = asyncio.run(idempotency_ledger.get_cached_result(temp_ledger, key))
        assert cached is not None
        assert cached["result_summary"] == "attempt-0"

    def test_result_summary_truncated_to_500_chars(self, temp_ledger: FastAPI):
        key = "big-summary"
        asyncio.run(
            idempotency_ledger.mark_completed(
                temp_ledger,
                key=key,
                conversation_id="c",
                leaf_event_id="l",
                tool_name="write_note",
                arguments={},
                result_summary="x" * 2000,
            )
        )
        cached = asyncio.run(idempotency_ledger.get_cached_result(temp_ledger, key))
        assert cached is not None
        assert len(cached["result_summary"]) == 500

    def test_clear_conversation_scoped(self, temp_ledger: FastAPI):
        async def seed() -> None:
            for conv, key in (("conv-A", "kA1"), ("conv-A", "kA2"), ("conv-B", "kB1")):
                await idempotency_ledger.mark_completed(
                    temp_ledger,
                    key=key,
                    conversation_id=conv,
                    leaf_event_id="l",
                    tool_name="write_note",
                    arguments={"k": key},
                )

        asyncio.run(seed())
        deleted = asyncio.run(
            idempotency_ledger.clear_conversation(temp_ledger, "conv-A")
        )
        assert deleted == 2
        assert asyncio.run(idempotency_ledger.has_completed(temp_ledger, "kA1")) is False
        assert asyncio.run(idempotency_ledger.has_completed(temp_ledger, "kA2")) is False
        assert asyncio.run(idempotency_ledger.has_completed(temp_ledger, "kB1")) is True


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_get_conn_raises_when_not_initialised(self):
        app = FastAPI()
        with pytest.raises(RuntimeError, match="not initialised"):
            idempotency_ledger._get_conn(app)  # type: ignore[arg-type]

    def test_close_db_is_idempotent(self, tmp_path, monkeypatch):
        db_path = tmp_path / "l.db"
        monkeypatch.setattr(idempotency_ledger, "DB_PATH", db_path)
        app = FastAPI()
        asyncio.run(idempotency_ledger.init_db(app))
        asyncio.run(idempotency_ledger.close_db(app))
        # Second close is a no-op.
        asyncio.run(idempotency_ledger.close_db(app))

    def test_survives_process_restart(self, tmp_path, monkeypatch):
        """A separate app instance sharing the same DB_PATH sees prior rows.

        This is the pure-SQLite half of the crash-and-resume test; the
        end-to-end crash-and-resume proof lives in
        scripts/test-crash-resume.sh.
        """
        db_path = tmp_path / "durable.db"
        monkeypatch.setattr(idempotency_ledger, "DB_PATH", db_path)

        app1 = FastAPI()
        asyncio.run(idempotency_ledger.init_db(app1))
        key = idempotency_ledger.compute_idempotency_key(
            "conv-1", "leaf-1", "write_note", {"title": "durable"}
        )
        asyncio.run(
            idempotency_ledger.mark_completed(
                app1,
                key=key,
                conversation_id="conv-1",
                leaf_event_id="leaf-1",
                tool_name="write_note",
                arguments={"title": "durable"},
                result_summary="ok",
                result_json={"ok": True},
            )
        )
        asyncio.run(idempotency_ledger.close_db(app1))

        # Simulate process restart with a fresh app + fresh connection.
        app2 = FastAPI()
        asyncio.run(idempotency_ledger.init_db(app2))
        try:
            assert asyncio.run(idempotency_ledger.has_completed(app2, key))
            cached = asyncio.run(
                idempotency_ledger.get_cached_result(app2, key)
            )
            assert cached is not None
            assert cached["result_json"] == {"ok": True}
        finally:
            asyncio.run(idempotency_ledger.close_db(app2))
