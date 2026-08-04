"""LLM-driven fix proposer.

For every failing :class:`~.harness.TaskOutcome`, the proposer:
1. Pulls the trajectory record for the run (verify iterations, diffs, task
   description) from the local :class:`~openhands_tools_ext.trajectory.store.TrajectoryStore`.
2. Sends a compact JSON summary to the planner-role LLM via the
   OpenAI-compatible ``/v1/chat/completions`` endpoint on the planner vLLM
   server (default ``http://localhost:8511``).
3. Writes the LLM's response verbatim to ``docs/proposals/YYYY-MM-DD-<task_id>-<run_id_short>.md``.

Never auto-applies proposals. Never overwrites an existing proposal file.
Human review is a hard invariant.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from openhands_tools_ext.selfeval.harness import TaskOutcome
from openhands_tools_ext.trajectory.store import TrajectoryStore, default_db_path

log = logging.getLogger(__name__)


PROPOSER_SYSTEM_PROMPT = """You are a senior software engineer reviewing an
overnight autonomous coding run that FAILED. You have the task the agent
attempted, the diffs it produced, and the verify step(s) that failed.

Produce EXACTLY ONE narrowly-scoped fix proposal in Markdown:

# Root Cause
1-3 sentences. Cite specific evidence from the verify output or diffs.

# Proposed Fix
Exact file paths + specific code changes. If a change is speculative,
say so explicitly. Prefer the smallest possible change.

# Risks
List anything the fix could break. If none, write "None identified."

# Confidence
"low" | "medium" | "high". Explain in one sentence.

Rules:
- Do NOT suggest running the run again as the fix.
- Do NOT propose sweeping refactors.
- Do NOT reference files you haven't seen evidence for.
- If the evidence is insufficient to propose ANY fix, output only:
  "# Root Cause\\nInsufficient evidence." — do not fabricate."""


_PROPOSAL_DIR = Path("docs/proposals")
_PLANNER_URL_ENV = "FORGE_SELFEVAL_PROPOSER_URL"
_PLANNER_MODEL_ENV = "FORGE_SELFEVAL_PROPOSER_MODEL"


def _short(run_id: str, n: int = 8) -> str:
    return run_id[:n] if run_id else "unknown"


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "task"


def _proposal_path(task_id: str, run_id: str, *, now: datetime | None = None) -> Path:
    when = now or datetime.now(timezone.utc)
    stem = f"{when:%Y-%m-%d}-{_slugify(task_id)}-{_short(run_id)}"
    return _PROPOSAL_DIR / f"{stem}.md"


def _build_context(
    outcome: TaskOutcome,
    store: TrajectoryStore,
) -> dict[str, Any]:
    """Build the compact JSON blob sent to the LLM. Trajectory-record fields
    are best-effort — the record may not exist for early-failure runs."""
    ctx: dict[str, Any] = {
        "task_id": outcome.task_id,
        "run_id": outcome.run_id,
        "harness_verdict": outcome.verdict,
        "harness_failure_detail": outcome.failure_detail,
        "trajectory_final_status": outcome.trajectory_status,
        "latest_verify_verdict": outcome.verify_verdict,
    }
    if not outcome.run_id:
        return ctx
    rec = store.get_by_run(outcome.run_id)
    if rec is None:
        ctx["_note"] = "no trajectory record found for run"
        return ctx
    ctx["task_description"] = getattr(rec, "task_description", "") or ""
    verify_iters = getattr(rec, "verify_iterations", []) or []
    ctx["verify_iterations"] = [
        {
            "iteration": getattr(v, "iteration", None),
            "verdict": getattr(getattr(v, "verdict", None), "value", None)
            or getattr(v, "verdict", None),
            "runner": getattr(getattr(v, "runner", None), "value", None)
            or getattr(v, "runner", None),
            "stderr_tail": (getattr(v, "stderr_tail", "") or "")[-2000:],
            "stdout_tail": (getattr(v, "stdout_tail", "") or "")[-2000:],
        }
        for v in verify_iters[-3:]  # last 3 iterations only
    ]
    diffs = getattr(rec, "diffs", []) or []
    # TrajectoryDiff stores per-file summaries, not raw patches — see
    # ``openhands_tools_ext/trajectory/schema.py::TrajectoryDiff``. The raw
    # unified diff is recoverable from the workspace git history if the
    # human wants it; we ship the summary shape to keep proposer prompts small.
    ctx["diffs"] = [
        {
            "path": getattr(d, "path", ""),
            "lines_added": getattr(d, "lines_added", 0),
            "lines_removed": getattr(d, "lines_removed", 0),
            "summary": getattr(d, "summary", ""),
        }
        for d in diffs
    ]
    ctx["repograph_symbols"] = list(getattr(rec, "repograph_symbols", []) or [])[:20]
    return ctx


def _planner_base_url() -> str:
    return os.environ.get(_PLANNER_URL_ENV, os.environ.get("LLM_PLANNER_URL", "http://localhost:8511"))


def _planner_model() -> str:
    return os.environ.get(_PLANNER_MODEL_ENV, "qwen3-thinking-2507-awq")


def _call_planner(context: dict[str, Any]) -> str:
    """Call the planner vLLM ``/v1/chat/completions`` endpoint. Returns the
    raw assistant message content, or a fallback message on error."""
    body = {
        "model": _planner_model(),
        "messages": [
            {"role": "system", "content": PROPOSER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, indent=2, default=str)},
        ],
        "max_tokens": 2048,
        "temperature": 0.2,
    }
    url = _planner_base_url().rstrip("/") + "/v1/chat/completions"
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=body, headers={"Authorization": "Bearer vllm"})
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        log.error("proposer: planner call failed: %s", exc)
        return f"# Root Cause\nProposer LLM call failed: {exc}\n"
    try:
        return payload["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        log.error("proposer: malformed planner response: %s (payload=%r)", exc, payload)
        return "# Root Cause\nProposer LLM returned a malformed response.\n"


def _write_proposal(
    proposal_dir: Path,
    outcome: TaskOutcome,
    context: dict[str, Any],
    body: str,
    *,
    now: datetime | None = None,
) -> Path:
    """Write the proposal to disk. Never overwrites; appends a numeric suffix
    on collision so a re-run of the same day preserves history."""
    proposal_dir.mkdir(parents=True, exist_ok=True)
    base = _proposal_path(outcome.task_id, outcome.run_id, now=now)
    target = proposal_dir / base.name
    if target.exists():
        i = 2
        while (proposal_dir / f"{base.stem}-v{i}.md").exists():
            i += 1
        target = proposal_dir / f"{base.stem}-v{i}.md"
    header = (
        f"<!-- forge-oh selfeval proposal\n"
        f"task_id: {outcome.task_id}\n"
        f"run_id: {outcome.run_id}\n"
        f"harness_verdict: {outcome.verdict}\n"
        f"generated_at: {(now or datetime.now(timezone.utc)).isoformat()}\n"
        f"-->\n\n"
    )
    context_dump = "\n\n<details><summary>Context sent to proposer</summary>\n\n```json\n" + json.dumps(
        context, indent=2, default=str
    ) + "\n```\n\n</details>\n"
    target.write_text(header + body.strip() + "\n" + context_dump, encoding="utf-8")
    return target


def propose_fixes(
    outcomes: list[TaskOutcome],
    *,
    proposal_dir: Path | None = None,
    trajectory_store: TrajectoryStore | None = None,
    now: datetime | None = None,
) -> list[Path]:
    """Generate one proposal file per non-passing outcome.

    Passing outcomes are skipped silently. Errored + timeout + failed all
    trigger a proposal — the LLM decides whether the evidence is enough.

    Returns the list of files written.
    """
    dir_ = proposal_dir or _PROPOSAL_DIR
    store = trajectory_store or TrajectoryStore(default_db_path())
    written: list[Path] = []
    for outcome in outcomes:
        if outcome.verdict == "passed":
            continue
        context = _build_context(outcome, store)
        body = _call_planner(context)
        path = _write_proposal(dir_, outcome, context, body, now=now)
        log.info(
            "proposer: %s → %s (verdict=%s)",
            outcome.task_id,
            path,
            outcome.verdict,
        )
        written.append(path)
    return written


def _outcomes_from_dicts(dicts: list[dict[str, Any]]) -> list[TaskOutcome]:
    """Rehydrate outcomes from a JSON summary. Extra keys are ignored."""
    fields = TaskOutcome.__dataclass_fields__.keys()
    return [TaskOutcome(**{k: d[k] for k in fields if k in d}) for d in dicts]


def dump_summary(summary_obj: Any, path: Path) -> Path:
    """Persist a :class:`~.harness.SelfEvalSummary` (or its ``to_dict()``) to JSON."""
    payload = summary_obj.to_dict() if hasattr(summary_obj, "to_dict") else asdict(summary_obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
