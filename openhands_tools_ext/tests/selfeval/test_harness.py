"""Tests for the self-eval harness orchestrator.

Uses ``httpx.MockTransport`` to stub the BFF; uses a real
:class:`TrajectoryStore` seeded via its public insert path.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import httpx
import pytest

from openhands_tools_ext.selfeval.harness import (
    SelfEvalSummary,
    _lookup_trajectory,
    _score,
    run_selfeval,
)
from openhands_tools_ext.selfeval.manifest import SelfEvalTask
from openhands_tools_ext.trajectory.schema import (
    TrajectoryRecord,
    TrajectoryStatus,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore
from openhands_tools_ext.verify.schema import (
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
)


def _task(id_: str = "t1") -> SelfEvalTask:
    return SelfEvalTask(
        id=id_,
        role="coder",
        task_complexity="single_action",
        prompt="do a thing",
        workspace_id="ws-abc",
        tags=[],
    )


class TestScore:
    def test_timeout(self) -> None:
        v, _ = _score("running", True, None, None)
        assert v == "timeout"

    def test_verify_fail(self) -> None:
        v, d = _score("succeeded", False, "success", "fail")
        assert v == "failed"
        assert "verify" in d

    def test_verify_error(self) -> None:
        v, _ = _score("succeeded", False, "success", "error")
        assert v == "failed"

    def test_trajectory_failed(self) -> None:
        v, d = _score("succeeded", False, TrajectoryStatus.FAILED.value, None)
        assert v == "failed"
        assert "trajectory" in d

    def test_trajectory_aborted(self) -> None:
        v, _ = _score("succeeded", False, TrajectoryStatus.ABORTED.value, None)
        assert v == "failed"

    def test_bff_failed(self) -> None:
        v, _ = _score("failed", False, None, None)
        assert v == "failed"

    def test_succeeded(self) -> None:
        v, d = _score("succeeded", False, TrajectoryStatus.SUCCESS.value, "pass")
        assert v == "passed"
        assert d == ""

    def test_succeeded_no_verify(self) -> None:
        v, _ = _score("succeeded", False, None, None)
        assert v == "passed"


class TestLookupTrajectory:
    def test_missing_record(self, tmp_path: Path) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        status, verdict = _lookup_trajectory(store, "no-such-run")
        assert (status, verdict) == (None, None)

    def test_reads_final_status_and_latest_verify(self, tmp_path: Path) -> None:
        store = TrajectoryStore(tmp_path / "traj.db")
        rec = TrajectoryRecord(
            trajectory_id=uuid.uuid4().hex,
            run_id="run-1",
            session_id="run-1",
            task_description="do a thing",
            final_status=TrajectoryStatus.VERIFIED_FAILURE,
            created_at="2026-08-03T22:00:00Z",
            verify_iterations=[
                VerificationStep(
                    iteration=1,
                    max_iterations=3,
                    verdict=VerifyVerdict.FAIL,
                    runner=VerifyRunner.PYTEST,
                    exit_code=1,
                    duration_ms=120,
                    stderr_tail="AssertionError",
                ),
                VerificationStep(
                    iteration=2,
                    max_iterations=3,
                    verdict=VerifyVerdict.PASS,
                    runner=VerifyRunner.PYTEST,
                    exit_code=0,
                    duration_ms=100,
                ),
            ],
        )
        store.insert(rec)
        status, verdict = _lookup_trajectory(store, "run-1")
        assert status == TrajectoryStatus.VERIFIED_FAILURE.value
        assert verdict == VerifyVerdict.PASS.value


class _FakeBFF:
    """Scripted BFF: takes a queue of (path, status_code, json) tuples."""

    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], list[dict]] = {}

    def script(self, method: str, path: str, *responses: dict) -> None:
        self._responses[(method, path)] = list(responses)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        queue = self._responses.get(key)
        if not queue:
            return httpx.Response(500, json={"error": f"unscripted {key}"})
        entry = queue.pop(0) if len(queue) > 1 else queue[0]
        return httpx.Response(entry.get("status", 200), json=entry.get("json", {}))


def _client(transport: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_run_selfeval_all_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bff = _FakeBFF()
    bff.script(
        "POST",
        "/api/runs",
        {"json": {"data": {"id": "run-1", "status": "queued"}}},
    )
    bff.script(
        "GET",
        "/api/runs/run-1",
        {"json": {"data": {"id": "run-1", "status": "succeeded"}}},
    )
    transport = httpx.MockTransport(bff)

    # Patch httpx.AsyncClient(base_url=...) inside harness to use transport.
    orig_ctor = httpx.AsyncClient

    def _patched_ctor(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_ctor(*args, **kwargs)

    monkeypatch.setattr("openhands_tools_ext.selfeval.harness.httpx.AsyncClient", _patched_ctor)

    store = TrajectoryStore(tmp_path / "traj.db")
    summary = await run_selfeval(
        [_task("t1")],
        bff_base_url="http://test",
        manifest_path="mem",
        selection_strategy="head",
        task_timeout_sec=10,
        trajectory_store=store,
        preset_id="ap-test",
    )
    assert isinstance(summary, SelfEvalSummary)
    assert summary.tasks_selected == 1
    assert summary.tasks_passed == 1
    assert summary.outcomes[0].verdict == "passed"


@pytest.mark.asyncio
async def test_run_selfeval_bff_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bff = _FakeBFF()
    bff.script(
        "POST",
        "/api/runs",
        {"status": 500, "json": {"detail": "boom"}},
    )
    transport = httpx.MockTransport(bff)
    orig_ctor = httpx.AsyncClient

    def _patched_ctor(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_ctor(*args, **kwargs)

    monkeypatch.setattr("openhands_tools_ext.selfeval.harness.httpx.AsyncClient", _patched_ctor)

    store = TrajectoryStore(tmp_path / "traj.db")
    summary = await run_selfeval(
        [_task("t1")],
        bff_base_url="http://test",
        manifest_path="mem",
        selection_strategy="head",
        task_timeout_sec=5,
        trajectory_store=store,
        preset_id="ap-test",
    )
    assert summary.tasks_errored == 1
    assert summary.outcomes[0].verdict == "error"
    assert "500" in summary.outcomes[0].failure_detail


@pytest.mark.asyncio
async def test_run_selfeval_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bff = _FakeBFF()
    bff.script(
        "POST",
        "/api/runs",
        {"json": {"data": {"id": "run-1", "status": "queued"}}},
    )
    bff.script(
        "GET",
        "/api/runs/run-1",
        {"json": {"data": {"id": "run-1", "status": "running"}}},
    )
    transport = httpx.MockTransport(bff)
    orig_ctor = httpx.AsyncClient

    def _patched_ctor(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_ctor(*args, **kwargs)

    monkeypatch.setattr("openhands_tools_ext.selfeval.harness.httpx.AsyncClient", _patched_ctor)

    # Also shrink asyncio.sleep so the poll loop runs fast enough to time out.
    # Capture the REAL asyncio.sleep before monkey-patching so we don't recurse
    # into our own patched version.
    _real_sleep = asyncio.sleep

    async def _fast_sleep(_):
        await _real_sleep(0)

    monkeypatch.setattr("openhands_tools_ext.selfeval.harness.asyncio.sleep", _fast_sleep)

    store = TrajectoryStore(tmp_path / "traj.db")
    summary = await run_selfeval(
        [_task("t1")],
        bff_base_url="http://test",
        manifest_path="mem",
        selection_strategy="head",
        task_timeout_sec=1,  # 1-second wall
        trajectory_store=store,
        preset_id="ap-test",
    )
    assert summary.tasks_timed_out == 1
    assert summary.outcomes[0].verdict == "timeout"
