"""Stage 6.4c (ADR-026 §Storage) — event_commit_ledger unit tests.

Covers the pure aiosqlite service in bff/services/event_commit_ledger.py:
  * init_db / close_db lifecycle
  * record_sha writes and roundtrips through get_sha
  * INSERT OR REPLACE semantics on duplicate (run_id, event_id)
  * bulk_get_shas returns hits only, missing ids absent
  * bulk_get_shas handles empty input
  * bulk_get_shas chunks correctly beyond the 500-per-query threshold
  * delete_run removes rows for that run and only that run
  * record_sha raises ValueError on empty run_id, event_id, commit_sha
  * schema: primary key (run_id, event_id) + idx_evshas_run index

Uses a temp-directory DB per test to keep the on-disk sidecar isolated.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI

from bff.services import event_commit_ledger


@pytest.fixture
def temp_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install a temp DB_PATH and yield an initialised FastAPI app."""
    db_path = tmp_path / "event_commit_ledger.db"
    monkeypatch.setattr(event_commit_ledger, "DB_PATH", db_path)
    app = FastAPI()
    asyncio.run(event_commit_ledger.init_db(app))
    try:
        yield app
    finally:
        asyncio.run(event_commit_ledger.close_db(app))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_table_and_index_created(self, temp_ledger: FastAPI):
        async def _check():
            conn = temp_ledger.state.event_commit_db
            # Table exists.
            async with conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='event_commit_shas'"
            ) as cur:
                row = await cur.fetchone()
            assert row is not None, "event_commit_shas table missing"
            # Composite PK.
            async with conn.execute(
                "PRAGMA table_info(event_commit_shas)"
            ) as cur:
                cols = await cur.fetchall()
            pk_cols = sorted([c["name"] for c in cols if c["pk"] > 0])
            assert pk_cols == ["event_id", "run_id"], f"unexpected PK: {pk_cols}"
            # Index exists.
            async with conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_evshas_run'"
            ) as cur:
                idx = await cur.fetchone()
            assert idx is not None, "idx_evshas_run missing"

        asyncio.run(_check())


# ---------------------------------------------------------------------------
# Write + read roundtrip
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_then_get_returns_sha(self, temp_ledger: FastAPI):
        async def _run():
            await event_commit_ledger.record_sha(
                temp_ledger,
                run_id="run-abc",
                event_id="evt-1",
                commit_sha="deadbeef" * 5,
            )
            sha = await event_commit_ledger.get_sha(temp_ledger, "evt-1")
            assert sha == "deadbeef" * 5

        asyncio.run(_run())

    def test_get_sha_missing_returns_none(self, temp_ledger: FastAPI):
        async def _run():
            sha = await event_commit_ledger.get_sha(temp_ledger, "never-recorded")
            assert sha is None

        asyncio.run(_run())

    def test_get_sha_empty_event_id_returns_none(self, temp_ledger: FastAPI):
        async def _run():
            assert await event_commit_ledger.get_sha(temp_ledger, "") is None

        asyncio.run(_run())

    def test_insert_or_replace_on_duplicate(self, temp_ledger: FastAPI):
        async def _run():
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="run-1", event_id="evt-1", commit_sha="aaa"
            )
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="run-1", event_id="evt-1", commit_sha="bbb"
            )
            assert await event_commit_ledger.get_sha(temp_ledger, "evt-1") == "bbb"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bulk lookup
# ---------------------------------------------------------------------------


class TestBulkGetShas:
    def test_bulk_returns_hits_only(self, temp_ledger: FastAPI):
        async def _run():
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="r1", event_id="e1", commit_sha="sha-1"
            )
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="r1", event_id="e2", commit_sha="sha-2"
            )
            got = await event_commit_ledger.bulk_get_shas(
                temp_ledger, ["e1", "e2", "missing"]
            )
            assert got == {"e1": "sha-1", "e2": "sha-2"}

        asyncio.run(_run())

    def test_bulk_empty_input(self, temp_ledger: FastAPI):
        async def _run():
            assert await event_commit_ledger.bulk_get_shas(temp_ledger, []) == {}

        asyncio.run(_run())

    def test_bulk_chunks_beyond_threshold(self, temp_ledger: FastAPI):
        async def _run():
            # Insert 1200 rows to force the CHUNK=500 loop to iterate 3 times.
            for i in range(1200):
                await event_commit_ledger.record_sha(
                    temp_ledger,
                    run_id="rBig",
                    event_id=f"e{i}",
                    commit_sha=f"sha-{i}",
                )
            ids = [f"e{i}" for i in range(1200)]
            got = await event_commit_ledger.bulk_get_shas(temp_ledger, ids)
            assert len(got) == 1200
            assert got["e0"] == "sha-0"
            assert got["e1199"] == "sha-1199"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteRun:
    def test_delete_run_removes_matching_rows_only(self, temp_ledger: FastAPI):
        async def _run():
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="rA", event_id="e1", commit_sha="a1"
            )
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="rA", event_id="e2", commit_sha="a2"
            )
            await event_commit_ledger.record_sha(
                temp_ledger, run_id="rB", event_id="e3", commit_sha="b3"
            )
            n = await event_commit_ledger.delete_run(temp_ledger, "rA")
            assert n == 2
            assert await event_commit_ledger.get_sha(temp_ledger, "e1") is None
            assert await event_commit_ledger.get_sha(temp_ledger, "e2") is None
            # rB's row still there.
            assert await event_commit_ledger.get_sha(temp_ledger, "e3") == "b3"

        asyncio.run(_run())

    def test_delete_unknown_run_returns_zero(self, temp_ledger: FastAPI):
        async def _run():
            assert await event_commit_ledger.delete_run(temp_ledger, "never") == 0

        asyncio.run(_run())

    def test_delete_empty_run_id_returns_zero(self, temp_ledger: FastAPI):
        async def _run():
            assert await event_commit_ledger.delete_run(temp_ledger, "") == 0

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_record_sha_empty_run_id_raises(self, temp_ledger: FastAPI):
        async def _run():
            with pytest.raises(ValueError, match="run_id is required"):
                await event_commit_ledger.record_sha(
                    temp_ledger, run_id="", event_id="e1", commit_sha="s1"
                )

        asyncio.run(_run())

    def test_record_sha_empty_event_id_raises(self, temp_ledger: FastAPI):
        async def _run():
            with pytest.raises(ValueError, match="event_id is required"):
                await event_commit_ledger.record_sha(
                    temp_ledger, run_id="r1", event_id="", commit_sha="s1"
                )

        asyncio.run(_run())

    def test_record_sha_empty_commit_sha_raises(self, temp_ledger: FastAPI):
        async def _run():
            with pytest.raises(ValueError, match="commit_sha is required"):
                await event_commit_ledger.record_sha(
                    temp_ledger, run_id="r1", event_id="e1", commit_sha=""
                )

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Uninitialised DB guard
# ---------------------------------------------------------------------------


class TestUninitialisedGuard:
    def test_record_before_init_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Build an app but never call init_db.
        monkeypatch.setattr(
            event_commit_ledger, "DB_PATH", tmp_path / "unused.db"
        )
        app = FastAPI()

        async def _run():
            with pytest.raises(RuntimeError, match="DB not initialised"):
                await event_commit_ledger.record_sha(
                    app, run_id="r1", event_id="e1", commit_sha="s1"
                )

        asyncio.run(_run())
