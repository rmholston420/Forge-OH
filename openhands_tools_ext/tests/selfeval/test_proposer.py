"""Tests for the selfeval proposer.

Uses ``httpx.MockTransport`` for the planner call and a real
:class:`TrajectoryStore` seeded via ``insert``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from openhands_tools_ext.selfeval.harness import TaskOutcome
from openhands_tools_ext.selfeval import proposer
from openhands_tools_ext.trajectory.schema import (
    TrajectoryDiff,
    TrajectoryRecord,
    TrajectoryStatus,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore
from openhands_tools_ext.verify.schema import (
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
)


FIXED_NOW = datetime(2026, 8, 3, 22, 30, tzinfo=timezone.utc)


def _seed_traj(store: TrajectoryStore, run_id: str) -> None:
    rec = TrajectoryRecord(
        trajectory_id=uuid.uuid4().hex,
        run_id=run_id,
        session_id=run_id,
        task_description="write add_two(a,b)",
        final_status=TrajectoryStatus.VERIFIED_FAILURE,
        created_at="2026-08-03T22:00:00Z",
        diffs=[TrajectoryDiff(path="add.py", lines_added=3, lines_removed=0, summary="add add_two")],
        verify_iterations=[
            VerificationStep(
                iteration=1,
                max_iterations=3,
                verdict=VerifyVerdict.FAIL,
                runner=VerifyRunner.PYTEST,
                exit_code=1,
                duration_ms=100,
                stderr_tail="AssertionError: expected 5 got 6",
            )
        ],
    )
    store.insert(rec)


def _outcome(task_id: str = "t1", run_id: str = "run-1", verdict: str = "failed") -> TaskOutcome:
    return TaskOutcome(
        task_id=task_id,
        run_id=run_id,
        verdict=verdict,  # type: ignore[arg-type]
        duration_sec=12.3,
        trajectory_status=TrajectoryStatus.VERIFIED_FAILURE.value,
        verify_verdict=VerifyVerdict.FAIL.value,
        failure_detail="verify verdict='fail'",
    )


class TestProposalPathAndWriting:
    def test_path_shape(self) -> None:
        p = proposer._proposal_path("smoke-add-two", "abcd1234efgh", now=FIXED_NOW)
        assert p.name == "2026-08-03-smoke-add-two-abcd1234.md"

    def test_writes_and_never_overwrites(self, tmp_path: Path) -> None:
        oc = _outcome()
        first = proposer._write_proposal(tmp_path, oc, {"k": "v"}, "# Root Cause\nx.\n", now=FIXED_NOW)
        second = proposer._write_proposal(tmp_path, oc, {"k": "v"}, "# Root Cause\ny.\n", now=FIXED_NOW)
        assert first != second
        assert second.name.endswith("-v2.md")

    def test_writes_metadata_header(self, tmp_path: Path) -> None:
        oc = _outcome()
        p = proposer._write_proposal(tmp_path, oc, {"context_key": "ctx"}, "# Root Cause\nhi.\n", now=FIXED_NOW)
        text = p.read_text(encoding="utf-8")
        assert "task_id: t1" in text
        assert "run_id: run-1" in text
        assert "harness_verdict: failed" in text
        assert "context_key" in text  # context dump is embedded


class TestBuildContext:
    def test_no_run_id_returns_minimal(self, tmp_path: Path) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        oc = _outcome(run_id="", verdict="error")
        ctx = proposer._build_context(oc, store)
        assert ctx["task_id"] == "t1"
        assert "diffs" not in ctx

    def test_missing_trajectory(self, tmp_path: Path) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        ctx = proposer._build_context(_outcome(), store)
        assert ctx.get("_note") == "no trajectory record found for run"

    def test_full_context(self, tmp_path: Path) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        _seed_traj(store, "run-1")
        ctx = proposer._build_context(_outcome(), store)
        assert ctx["task_description"] == "write add_two(a,b)"
        assert ctx["verify_iterations"][0]["verdict"] == VerifyVerdict.FAIL.value
        assert "AssertionError" in ctx["verify_iterations"][0]["stderr_tail"]
        assert ctx["diffs"][0]["path"] == "add.py"


class TestProposeFixes:
    def test_skips_passing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        _seed_traj(store, "run-1")

        called = {"n": 0}
        def _stub(_ctx):
            called["n"] += 1
            return "# Root Cause\nx.\n"
        monkeypatch.setattr(proposer, "_call_planner", _stub)

        passing = _outcome(verdict="passed")
        written = proposer.propose_fixes(
            [passing], proposal_dir=tmp_path, trajectory_store=store, now=FIXED_NOW
        )
        assert written == []
        assert called["n"] == 0

    def test_writes_for_failed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        _seed_traj(store, "run-1")

        monkeypatch.setattr(
            proposer, "_call_planner", lambda _ctx: "# Root Cause\nMissing base case.\n"
        )

        written = proposer.propose_fixes(
            [_outcome()], proposal_dir=tmp_path, trajectory_store=store, now=FIXED_NOW
        )
        assert len(written) == 1
        assert "Missing base case" in written[0].read_text(encoding="utf-8")


class TestPlannerHTTP:
    def test_transport_error_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(request):
            raise httpx.ConnectError("cannot reach planner", request=request)
        monkeypatch.setenv("FORGE_SELFEVAL_PROPOSER_URL", "http://test")
        transport = httpx.MockTransport(_raise)

        orig_ctor = httpx.Client
        def _patched(*args, **kwargs):
            kwargs["transport"] = transport
            return orig_ctor(*args, **kwargs)
        monkeypatch.setattr(proposer.httpx, "Client", _patched)

        body = proposer._call_planner({"task_id": "t1"})
        assert "Proposer LLM call failed" in body

    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {"choices": [{"message": {"content": "# Root Cause\nBecause X.\n"}}]}
        def _handler(request):
            body = json.loads(request.content)
            assert body["model"]
            assert body["messages"][0]["role"] == "system"
            return httpx.Response(200, json=payload)
        transport = httpx.MockTransport(_handler)
        orig_ctor = httpx.Client
        def _patched(*args, **kwargs):
            kwargs["transport"] = transport
            return orig_ctor(*args, **kwargs)
        monkeypatch.setattr(proposer.httpx, "Client", _patched)
        monkeypatch.setenv("FORGE_SELFEVAL_PROPOSER_URL", "http://test")

        body = proposer._call_planner({"task_id": "t1"})
        assert "Because X" in body
