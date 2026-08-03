"""Run-completion hook CLI (Slice F.5b, Rec #3).

Invoked as::

    python -m openhands_tools_ext.trajectory.hook

The OpenHands SDK's ``HookType.COMMAND`` contract runs a subprocess
with the ``HookEvent`` payload on stdin. This hook is registered
alongside (not instead of) the verify STOP hook; when a STOP event
fires it materializes a :class:`TrajectoryRecord` from what's
observable in the workspace and persists it via
:class:`TrajectoryWriter`.

Sources of record fields (all best-effort):

* **verify-state.json** — the verify hook's per-session state. Gives
  us ``last_verdict`` (→ ``final_status``) and the ``edited_files``
  list.
* **trajectory-sidecar.json** — optional companion the agent server
  or a preceding hook writes. When present, provides the natural
  language ``task_description``, ``plan``, ``symptom``,
  ``repograph_repo_key``, ``repograph_symbols``, and (typed) diffs.
* **Environment** — ``OPENHANDS_PROJECT_DIR`` for workspace,
  ``OPENHANDS_SESSION_ID`` and ``OPENHANDS_TASK`` as fallbacks.

Semantics (matching Claude Code's hook contract):

* Exit 0 with structured JSON on stdout → success.
* Exit 1 → non-blocking error. This hook never blocks.
* Non-STOP events are no-ops.

Optional inline indexing: setting ``FORGE_OH_TRAJECTORY_INDEX_INLINE=1``
runs :class:`TrajectoryIndexer` after the write, so the record is
searchable immediately. Otherwise a follow-up call (cron, next-turn
hook, or a manual pass) drains the queue.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from openhands_tools_ext.trajectory.schema import (
    TrajectoryDiff,
    TrajectoryStatus,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore
from openhands_tools_ext.trajectory.writer import (
    RunSummary,
    TrajectoryIndexer,
    TrajectoryWriter,
)

STATE_DIR = ".forge-oh"
VERIFY_STATE_FILE = "verify-state.json"
TRAJECTORY_SIDECAR_FILE = "trajectory-sidecar.json"


def _load_json(path: Path) -> dict[str, Any]:
    """Return dict payload from ``path`` or ``{}`` on missing/malformed."""
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_verify_state(workspace: Path, session_id: str) -> dict[str, Any]:
    """Read the verify hook's per-session state (may be empty)."""
    payload = _load_json(workspace / STATE_DIR / VERIFY_STATE_FILE)
    sess = payload.get(session_id)
    return sess if isinstance(sess, dict) else {}


def _load_sidecar(workspace: Path, session_id: str) -> dict[str, Any]:
    """Load the trajectory sidecar for this session.

    The sidecar file is a top-level dict keyed by session id (mirrors
    verify-state.json layout) so multiple sessions can coexist:

        {
          "<session_id>": {
            "task_description": "...",
            "plan": "...",
            "symptom": "...",
            "repograph_repo_key": "...",
            "repograph_symbols": ["a.b", ...],
            "diffs": [{"path": "a.py", "lines_added": 3, ...}]
          }
        }
    """
    payload = _load_json(workspace / STATE_DIR / TRAJECTORY_SIDECAR_FILE)
    sess = payload.get(session_id)
    return sess if isinstance(sess, dict) else {}


# Sidecar keys F.15 producers may set to record structured signals
# that outrank verify-state (e.g. an abort producer, a planner
# emitting an explicit final-status override).
_SIDECAR_FINAL_STATUS_KEY = "final_status"


_VERDICT_MAP: dict[str, TrajectoryStatus] = {
    # ``verify-state.json`` stores the raw verdict string
    # (VerificationStep.use_enum_values=True). Live systems have
    # historically written both bare (``pass``) and past-tense
    # (``passed``) forms depending on the verify driver — accept
    # both so a driver rename doesn't corrupt the DB.
    "pass": TrajectoryStatus.SUCCESS,
    "passed": TrajectoryStatus.SUCCESS,
    "fail": TrajectoryStatus.FAILED,
    "failed": TrajectoryStatus.FAILED,
    "error": TrajectoryStatus.FAILED,
    "errored": TrajectoryStatus.FAILED,
    # A ``no-step`` / ``skip`` / ``skipped`` verdict means verify
    # chose not to examine this run — not that the run itself was
    # unknown. See ``_infer_final_status`` for how we combine this
    # with the STOP hook's FINISHED precondition.
    "no-step": TrajectoryStatus.SUCCESS,
    "skip": TrajectoryStatus.SUCCESS,
    "skipped": TrajectoryStatus.SUCCESS,
}


def _verdict_to_status(verdict: str) -> TrajectoryStatus:
    """Map a verify verdict string to a :class:`TrajectoryStatus`.

    Kept as a pure lookup; callers that need the STOP-hook default
    semantics should use :func:`_infer_final_status` instead.
    """
    return _VERDICT_MAP.get(verdict, TrajectoryStatus.UNKNOWN)


def _coerce_sidecar_status(raw: object) -> TrajectoryStatus | None:
    """Accept an optional sidecar-provided final status.

    F.15 producers may write ``final_status`` into the sidecar as
    either a raw enum value (e.g. ``"aborted"``) or a
    :class:`TrajectoryStatus` instance. Any other value is treated as
    absent so a malformed sidecar can never corrupt the row.
    """
    if isinstance(raw, TrajectoryStatus):
        return raw
    if isinstance(raw, str):
        try:
            return TrajectoryStatus(raw)
        except ValueError:
            return None
    return None


def _infer_final_status(
    verify_state: dict[str, object],
    sidecar: dict[str, object],
) -> TrajectoryStatus:
    """Combine sidecar and verify signals into a terminal status.

    Precedence, highest first:

    1. A well-formed ``final_status`` in the sidecar. F.15 producers
       (abort handlers, planner failures, etc) use this to make an
       explicit terminal-state claim that outranks verify heuristics.
    2. An explicit verify verdict (``pass`` → SUCCESS,
       ``fail``/``error`` → FAILED).
    3. **STOP-hook default**: SUCCESS. The trajectory STOP hook only
       fires when the SDK reports ``execution_status == FINISHED``,
       i.e. the agent called ``finish`` on its own. In that case an
       absent or ``no-step``/``skip`` verify verdict means "verify
       had nothing to say" — not "the run's outcome is unknown".
       Attributing SUCCESS here matches every downstream retrieval
       assumption (``verified_only=True`` still filters out the
       explicit-failure rows).
    4. UNKNOWN for a garbled verdict string we can't parse. This is
       a genuine data-quality signal.
    """
    override = _coerce_sidecar_status(sidecar.get(_SIDECAR_FINAL_STATUS_KEY))
    if override is not None:
        return override

    verdict = verify_state.get("last_verdict")
    if not isinstance(verdict, str) or not verdict:
        # No verify-state file, or a file with no verdict field.
        # STOP-hook default applies.
        return TrajectoryStatus.SUCCESS

    if verdict in _VERDICT_MAP:
        return _VERDICT_MAP[verdict]

    # Unrecognized verdict string. Preserve UNKNOWN as an explicit
    # "we can't tell" signal so operators can spot data drift.
    return TrajectoryStatus.UNKNOWN


def _parse_diffs(raw: object) -> list[TrajectoryDiff]:
    """Coerce a JSON list of diff dicts into :class:`TrajectoryDiff` items."""
    if not isinstance(raw, list):
        return []
    out: list[TrajectoryDiff] = []
    for item in raw:
        if isinstance(item, TrajectoryDiff):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        try:
            out.append(TrajectoryDiff(**item))
        except Exception:  # noqa: S112
            # Best-effort: skip malformed diff entries rather than
            # failing the whole hook. Matches verify/hook.py's
            # treatment of malformed sidecar state.
            continue
    return out


def build_summary_from_sources(
    *,
    workspace: Path,
    session_id: str,
    run_id: str,
    env_task: str = "",
) -> RunSummary:
    """Assemble a :class:`RunSummary` from workspace state.

    Kept pure so tests can call it directly without spawning a
    subprocess.
    """
    verify_state = _load_verify_state(workspace, session_id)
    sidecar = _load_sidecar(workspace, session_id)

    task_description = str(sidecar.get("task_description") or env_task or "")
    plan = str(sidecar.get("plan") or "")
    symptom = str(sidecar.get("symptom") or "")
    repo_key = str(sidecar.get("repograph_repo_key") or "")

    raw_symbols = sidecar.get("repograph_symbols") or []
    symbols: list[str] = [str(s) for s in raw_symbols if isinstance(s, str)]

    diffs = _parse_diffs(sidecar.get("diffs"))

    verify_iterations = sidecar.get("verify_iterations") or []
    if not isinstance(verify_iterations, list):
        verify_iterations = []

    status = _infer_final_status(verify_state, sidecar)

    return RunSummary(
        run_id=run_id,
        session_id=session_id,
        task_description=task_description,
        plan=plan,
        diffs=diffs,
        verify_iterations=verify_iterations,
        symptom=symptom,
        final_status=status,
        repograph_repo_key=repo_key,
        repograph_symbols=symbols,
    )


def main(argv: list[str] | None = None) -> int:
    del argv  # unused; signature kept for testability
    raw = sys.stdin.read().strip()
    if not raw:
        sys.stderr.write("trajectory-hook: empty stdin (expected HookEvent JSON)\n")
        return 1
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"trajectory-hook: bad JSON on stdin: {exc}\n")
        return 1
    if not isinstance(event, dict):
        sys.stderr.write("trajectory-hook: stdin JSON must be an object\n")
        return 1

    if event.get("event_type") != "Stop":
        print(json.dumps({"reason": "trajectory-hook: non-STOP event ignored"}))
        return 0

    workspace_str = os.environ.get("OPENHANDS_PROJECT_DIR") or os.environ.get(
        "OPENHANDS_WORKING_DIR"
    )
    if not workspace_str:
        sys.stderr.write("trajectory-hook: OPENHANDS_PROJECT_DIR not set\n")
        return 1
    workspace = Path(workspace_str)

    session_id = os.environ.get("OPENHANDS_SESSION_ID") or event.get("session_id") or ""
    if not session_id:
        sys.stderr.write("trajectory-hook: no session id available\n")
        return 1

    # run_id defaults to session_id when the event doesn't carry a
    # distinct run key. Downstream this is only used as the primary
    # identifier for the record; it doesn't need to be globally unique
    # across sessions.
    run_id = str(event.get("run_id") or session_id)
    env_task = os.environ.get("OPENHANDS_TASK", "")

    summary = build_summary_from_sources(
        workspace=workspace,
        session_id=session_id,
        run_id=run_id,
        env_task=env_task,
    )

    store = TrajectoryStore()
    writer = TrajectoryWriter(store)
    record = writer.write_from_run(summary)

    indexed = 0
    if os.environ.get("FORGE_OH_TRAJECTORY_INDEX_INLINE") == "1":
        indexer = TrajectoryIndexer(store)
        indexed = indexer.index_pending()

    print(
        json.dumps(
            {
                "trajectory_id": record.trajectory_id,
                "run_id": record.run_id,
                "final_status": record.final_status,
                "indexed": indexed,
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
