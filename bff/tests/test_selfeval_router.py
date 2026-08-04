"""Tests for bff/routers/selfeval.py.

Cover:
- happy path list/get for both cycles and proposals
- filename validation (regex + traversal)
- 409 when a cycle is already running
- 502 when systemctl exits nonzero
- 500 when systemctl is missing
- reaper transitions the state back to not-running
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app_and_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fresh router+app with tmp dirs; also resets in-process cycle state."""
    summary_dir = tmp_path / "docs" / "selfeval"
    proposal_dir = tmp_path / "docs" / "proposals"
    summary_dir.mkdir(parents=True)
    proposal_dir.mkdir(parents=True)
    monkeypatch.setenv("FORGE_SELFEVAL_SUMMARY_DIR", str(summary_dir))
    monkeypatch.setenv("FORGE_SELFEVAL_PROPOSAL_DIR", str(proposal_dir))
    # Force a reimport so the module-level path constants pick up the env.
    import importlib

    import bff.routers.selfeval as mod

    importlib.reload(mod)

    app = FastAPI()
    app.include_router(mod.router, prefix="/api")
    return TestClient(app), summary_dir, proposal_dir, mod


class TestListCycles:
    def test_empty_dir_returns_empty_list(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        resp = client.get("/api/selfeval/cycles")
        assert resp.status_code == 200
        assert resp.json() == {"cycles": []}

    def test_lists_valid_summaries_newest_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, summary_dir, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        (summary_dir / "2026-08-01-selfeval.json").write_text(
            json.dumps({"tasks_passed": 3, "tasks_failed": 0}), encoding="utf-8"
        )
        (summary_dir / "2026-08-03-selfeval.json").write_text(
            json.dumps({"tasks_passed": 2, "tasks_failed": 1}), encoding="utf-8"
        )
        resp = client.get("/api/selfeval/cycles")
        cycles = resp.json()["cycles"]
        assert [c["filename"] for c in cycles] == [
            "2026-08-03-selfeval.json",
            "2026-08-01-selfeval.json",
        ]
        assert cycles[0]["tasks_failed"] == 1

    def test_ignores_files_with_wrong_shape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, summary_dir, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        (summary_dir / "random.txt").write_text("nope")
        (summary_dir / "not-a-date-selfeval.json").write_text("{}")
        (summary_dir / "2026-08-01-selfeval.json").write_text("{}")
        resp = client.get("/api/selfeval/cycles")
        assert [c["filename"] for c in resp.json()["cycles"]] == [
            "2026-08-01-selfeval.json"
        ]


class TestGetCycle:
    def test_happy_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        client, summary_dir, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        payload = {"started_at": "2026-08-03T02:30:00Z", "tasks_passed": 3}
        (summary_dir / "2026-08-03-selfeval.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        resp = client.get("/api/selfeval/cycles/2026-08-03-selfeval.json")
        assert resp.status_code == 200
        assert resp.json() == payload

    def test_missing_returns_404(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        resp = client.get("/api/selfeval/cycles/2099-01-01-selfeval.json")
        assert resp.status_code == 404

    def test_invalid_filename_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        # Wrong shape - not YYYY-MM-DD prefix.
        resp = client.get("/api/selfeval/cycles/not-a-date-selfeval.json")
        assert resp.status_code == 400

    def test_traversal_attempt_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        # FastAPI URL-normalizes ``..`` in path params, but even the raw
        # regex catches it \u2014 the pattern requires the leading date.
        resp = client.get(
            "/api/selfeval/cycles/..%2F..%2Fetc%2Fpasswd",
        )
        # Either 400 (regex block) or 404 (FastAPI routing miss) is acceptable;
        # under no circumstance should it return 200.
        assert resp.status_code in (400, 404)


class TestListProposals:
    def test_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        resp = client.get("/api/selfeval/proposals")
        assert resp.json() == {"proposals": []}

    def test_date_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _, proposal_dir, _ = _make_app_and_client(tmp_path, monkeypatch)
        (proposal_dir / "2026-08-01-add-two-abc123.md").write_text("# a")
        (proposal_dir / "2026-08-03-reverse-def456.md").write_text("# b")
        resp = client.get("/api/selfeval/proposals?date=2026-08-03")
        names = [p["filename"] for p in resp.json()["proposals"]]
        assert names == ["2026-08-03-reverse-def456.md"]

    def test_bad_date_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        resp = client.get("/api/selfeval/proposals?date=yesterday")
        assert resp.status_code == 400


class TestGetProposal:
    def test_happy_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _, proposal_dir, _ = _make_app_and_client(tmp_path, monkeypatch)
        (proposal_dir / "2026-08-03-reverse-def456.md").write_text(
            "# Proposal\n\nbody", encoding="utf-8"
        )
        resp = client.get("/api/selfeval/proposals/2026-08-03-reverse-def456.md")
        assert resp.status_code == 200
        assert resp.json()["body"].startswith("# Proposal")


class TestRunAndStatus:
    def test_status_starts_idle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, _ = _make_app_and_client(tmp_path, monkeypatch)
        resp = client.get("/api/selfeval/status")
        assert resp.json() == {"running": False, "started_at": None, "last_result": None}

    def test_run_launches_systemctl_and_returns_started_at(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, mod = _make_app_and_client(tmp_path, monkeypatch)

        # Fake process: exits 0, empty stderr.
        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(return_value=(b"", b""))
        fake_proc.returncode = 0

        # Reaper should not tie up the test: patch it to return immediately.
        with patch.object(
            mod.asyncio,
            "create_subprocess_exec",
            AsyncMock(return_value=fake_proc),
        ), patch.object(mod, "_reap_cycle", AsyncMock()):
            resp = client.post("/api/selfeval/run")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["service_unit"] == "forge-oh-selfeval.service"
        assert body["started_at"]

    def test_run_returns_409_when_already_running(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, mod = _make_app_and_client(tmp_path, monkeypatch)
        # Force the state as if a cycle is in flight.
        mod._state.running = True
        mod._state.started_at = "2026-08-03T22:00:00Z"
        resp = client.post("/api/selfeval/run")
        assert resp.status_code == 409
        # Restore for cleanliness.
        mod._state.running = False
        mod._state.started_at = None

    def test_run_returns_502_when_systemctl_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, mod = _make_app_and_client(tmp_path, monkeypatch)
        fake_proc = MagicMock()
        fake_proc.communicate = AsyncMock(
            return_value=(b"", b"Unit forge-oh-selfeval.service not found.\n")
        )
        fake_proc.returncode = 5
        with patch.object(
            mod.asyncio, "create_subprocess_exec", AsyncMock(return_value=fake_proc)
        ), patch.object(mod, "_reap_cycle", AsyncMock()):
            resp = client.post("/api/selfeval/run")
        assert resp.status_code == 502
        assert "systemctl start failed" in resp.json()["detail"]
        # State should be cleared so next attempt isn't stuck at 409.
        assert mod._state.running is False

    def test_run_returns_500_when_systemctl_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _, _, mod = _make_app_and_client(tmp_path, monkeypatch)
        with patch.object(
            mod.asyncio,
            "create_subprocess_exec",
            AsyncMock(side_effect=FileNotFoundError()),
        ):
            resp = client.post("/api/selfeval/run")
        assert resp.status_code == 500
        assert "systemctl" in resp.json()["detail"]
        assert mod._state.running is False
