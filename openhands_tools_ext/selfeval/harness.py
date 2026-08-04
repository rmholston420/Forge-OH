"""Self-Eval harness orchestrator.

For each selected :class:`~.manifest.SelfEvalTask`, the harness:
1. ``POST /api/runs`` on the BFF with the task's prompt/role/workspace.
2. Polls ``GET /api/runs/{id}`` until the run reaches a terminal status
   (``succeeded``, ``failed``) or the per-task timeout elapses.
3. Reads the newest matching :class:`~openhands_tools_ext.trajectory.schema.TrajectoryRecord`
   from the local trajectory store to extract the verify verdict.
4. Records a :class:`TaskOutcome` per task and rolls them into a :class:`SelfEvalSummary`.

The harness NEVER writes into workspaces itself, NEVER kills processes,
and NEVER retries. Failures propagate to :mod:`.proposer` for morning review.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from openhands_tools_ext.selfeval import SELFEVAL_PROVENANCE, SELFEVAL_TASK_TIMEOUT_SEC
from openhands_tools_ext.selfeval.manifest import SelfEvalTask
from openhands_tools_ext.trajectory.schema import TrajectoryStatus
from openhands_tools_ext.trajectory.store import TrajectoryStore, default_db_path

log = logging.getLogger(__name__)


# Terminal statuses per ``_STATUS_MAP`` in ``bff/routers/runs.py``.
_TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed"})


TaskVerdict = Literal["passed", "failed", "timeout", "error"]


@dataclass(frozen=True)
class TaskOutcome:
    """Result of running one manifest task through Forge-OH.

    Attributes
    ----------
    task_id : str
        Manifest task id (echoes :class:`SelfEvalTask.id`).
    run_id : str
        Agent-server conversation id, or empty string if creation failed.
    verdict : TaskVerdict
        - ``passed``: run reached ``succeeded`` and verify verdict was ``pass``
          (or no verify step ran but the run finished cleanly).
        - ``failed``: run finished but verify verdict was ``fail``/``error``,
          or the run itself finished in ``failed`` status.
        - ``timeout``: per-task wall-clock cap tripped before terminal.
        - ``error``: BFF/agent-server returned an unrecoverable error.
    duration_sec : float
        Wall-clock from POST /api/runs to terminal or timeout.
    trajectory_status : str | None
        The ``final_status`` field from the trajectory record, if one was found.
    verify_verdict : str | None
        Latest verify iteration's ``verdict`` field, if any.
    failure_detail : str
        Human-readable summary. Empty on ``passed``.
    """

    task_id: str
    run_id: str
    verdict: TaskVerdict
    duration_sec: float
    trajectory_status: str | None
    verify_verdict: str | None
    failure_detail: str


@dataclass(frozen=True)
class SelfEvalSummary:
    """Aggregate outcome for one self-eval cycle."""

    started_at: str
    finished_at: str
    manifest_path: str
    selection_strategy: str
    tasks_selected: int
    tasks_passed: int
    tasks_failed: int
    tasks_timed_out: int
    tasks_errored: int
    outcomes: list[TaskOutcome] = field(default_factory=list)
    provenance: str = SELFEVAL_PROVENANCE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["outcomes"] = [asdict(o) for o in self.outcomes]
        return d


async def _create_run(
    client: httpx.AsyncClient, task: SelfEvalTask
) -> tuple[str, str]:
    """POST /api/runs. Returns ``(run_id, error)``. ``error`` is empty on success."""
    body = {
        "title": f"[selfeval] {task.id}",
        "workspaceId": task.workspace_id,
        "taskPrompt": task.prompt,
        "taskComplexity": task.task_complexity,
        "role": task.role,
        "requireApproval": False,
    }
    try:
        resp = await client.post("/api/runs", json=body, timeout=30.0)
    except httpx.HTTPError as exc:
        return "", f"transport error: {exc}"
    if resp.status_code >= 400:
        return "", f"BFF returned {resp.status_code}: {resp.text[:200]}"
    data = (resp.json() or {}).get("data") or {}
    rid = data.get("id") or ""
    if not rid:
        route_err = ((data.get("routing") or {}).get("error")) or ""
        return "", f"no run id returned; routing_error={route_err!r}"
    return rid, ""


async def _poll_until_terminal(
    client: httpx.AsyncClient,
    run_id: str,
    *,
    timeout_sec: int,
    poll_interval_sec: float = 5.0,
) -> tuple[str, bool]:
    """Poll ``GET /api/runs/{id}`` until terminal or timeout.

    Returns ``(status, timed_out)``. If ``timed_out`` is ``True``, ``status``
    holds the last observed non-terminal status (or ``"unknown"``).
    """
    deadline = time.monotonic() + timeout_sec
    last_status = "unknown"
    while time.monotonic() < deadline:
        try:
            resp = await client.get(f"/api/runs/{run_id}", timeout=10.0)
            if resp.status_code < 400:
                data = (resp.json() or {}).get("data") or {}
                last_status = data.get("status") or last_status
                if last_status in _TERMINAL_STATUSES:
                    return last_status, False
        except httpx.HTTPError as exc:
            log.debug("poll %s transport error: %s", run_id, exc)
        await asyncio.sleep(poll_interval_sec)
    return last_status, True


def _lookup_trajectory(
    store: TrajectoryStore, run_id: str
) -> tuple[str | None, str | None]:
    """Return ``(final_status, latest_verify_verdict)`` from the trajectory DB.

    Best-effort. Missing record → ``(None, None)``. The trajectory hook may not
    have written a record if verify was skipped or the run crashed before
    the stop hooks ran.
    """
    try:
        rec = store.get_by_run(run_id)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("selfeval: trajectory lookup failed for %s: %s", run_id, exc)
        return None, None
    if rec is None:
        return None, None
    final_status = getattr(rec, "final_status", None)
    if hasattr(final_status, "value"):
        final_status = final_status.value
    verify_iterations = getattr(rec, "verify_iterations", []) or []
    latest_verdict: str | None = None
    if verify_iterations:
        v = getattr(verify_iterations[-1], "verdict", None)
        latest_verdict = v.value if hasattr(v, "value") else v
    return final_status, latest_verdict


def _score(
    terminal_status: str,
    timed_out: bool,
    traj_status: str | None,
    verify_verdict: str | None,
) -> tuple[TaskVerdict, str]:
    """Reduce raw signals into a single :data:`TaskVerdict` + detail string.

    Rules (in order):
    1. ``timed_out`` → ``timeout``.
    2. verify verdict of ``fail`` or ``error`` → ``failed``.
    3. trajectory ``final_status`` of ``failed``/``verified_failure``/``aborted`` → ``failed``.
    4. BFF terminal status ``failed`` → ``failed``.
    5. BFF terminal status ``succeeded`` → ``passed``.
    6. Anything else (should be unreachable) → ``error``.
    """
    if timed_out:
        return "timeout", f"per-task timeout tripped; last status={terminal_status!r}"
    if verify_verdict in ("fail", "error"):
        return "failed", f"verify verdict={verify_verdict!r}"
    fail_traj = {
        TrajectoryStatus.FAILED.value,
        TrajectoryStatus.VERIFIED_FAILURE.value,
        TrajectoryStatus.ABORTED.value,
    }
    if traj_status in fail_traj:
        return "failed", f"trajectory final_status={traj_status!r}"
    if terminal_status == "failed":
        return "failed", "BFF status=failed (no verify/trajectory detail)"
    if terminal_status == "succeeded":
        return "passed", ""
    return "error", f"unhandled state: status={terminal_status!r}, traj={traj_status!r}"


async def _run_one(
    client: httpx.AsyncClient,
    store: TrajectoryStore,
    task: SelfEvalTask,
    *,
    timeout_sec: int,
) -> TaskOutcome:
    started = time.monotonic()
    run_id, err = await _create_run(client, task)
    if err:
        return TaskOutcome(
            task_id=task.id,
            run_id="",
            verdict="error",
            duration_sec=time.monotonic() - started,
            trajectory_status=None,
            verify_verdict=None,
            failure_detail=err,
        )
    terminal_status, timed_out = await _poll_until_terminal(
        client, run_id, timeout_sec=timeout_sec
    )
    traj_status, verify_verdict = _lookup_trajectory(store, run_id)
    verdict, detail = _score(terminal_status, timed_out, traj_status, verify_verdict)
    return TaskOutcome(
        task_id=task.id,
        run_id=run_id,
        verdict=verdict,
        duration_sec=time.monotonic() - started,
        trajectory_status=traj_status,
        verify_verdict=verify_verdict,
        failure_detail=detail,
    )


async def run_selfeval(
    tasks: list[SelfEvalTask],
    *,
    bff_base_url: str,
    manifest_path: str,
    selection_strategy: str,
    task_timeout_sec: int = SELFEVAL_TASK_TIMEOUT_SEC,
    trajectory_store: TrajectoryStore | None = None,
) -> SelfEvalSummary:
    """Run every task in ``tasks`` sequentially and return the aggregate summary.

    Tasks run serially, not concurrently: agent-server on Colossus has one
    conversation loop, and vLLM has one resident model at a time (ADR-009
    §3a). Parallelism here would just cause supervisor swaps.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    store = trajectory_store or TrajectoryStore(default_db_path())
    outcomes: list[TaskOutcome] = []
    async with httpx.AsyncClient(base_url=bff_base_url, timeout=30.0) as client:
        for task in tasks:
            log.info("selfeval: starting task %s (role=%s)", task.id, task.role)
            outcome = await _run_one(client, store, task, timeout_sec=task_timeout_sec)
            log.info(
                "selfeval: task %s → %s (%.1fs) %s",
                task.id,
                outcome.verdict,
                outcome.duration_sec,
                outcome.failure_detail,
            )
            outcomes.append(outcome)
    finished_at = datetime.now(timezone.utc).isoformat()
    return SelfEvalSummary(
        started_at=started_at,
        finished_at=finished_at,
        manifest_path=manifest_path,
        selection_strategy=selection_strategy,
        tasks_selected=len(tasks),
        tasks_passed=sum(1 for o in outcomes if o.verdict == "passed"),
        tasks_failed=sum(1 for o in outcomes if o.verdict == "failed"),
        tasks_timed_out=sum(1 for o in outcomes if o.verdict == "timeout"),
        tasks_errored=sum(1 for o in outcomes if o.verdict == "error"),
        outcomes=outcomes,
    )
