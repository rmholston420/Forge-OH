"""Derive per-run plan / commands / artifacts from agent-server events.

The agent-server ``/api/conversations/{id}/events/search`` stream carries every
action the agent took and every observation the environment produced. Three
Forge-OH endpoints reshape that stream into UI-shaped lists:

* ``plan``      — ActionEvents where ``tool_name == "task_tracker"`` (the
                  OpenHands plan primitive). Each observation carries the
                  current set of tasks with status.
* ``commands``  — ActionEvents where ``tool_name`` matches a bash tool. Paired
                  with the matching ObservationEvent (by ``action_id``) for
                  stdout/exit_code/duration.
* ``artifacts`` — ActionEvents where ``tool_name == "file_editor"`` with a
                  mutating command (``create``, ``str_replace``, ``insert``,
                  ``undo_edit``). Every such action is one artifact of type
                  ``file_change``. Undo_edit produces an artifact too so the UI
                  can show reversal history.

All three functions operate on the same in-memory events list returned by
``_fetch_all_events`` and are pure — no I/O, no dependency on ``get_client``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

# Tool-name buckets ---------------------------------------------------------
_BASH_TOOLS = {"execute_bash", "terminal", "bash", "run_bash", "start_bash_command"}
_FILE_TOOLS = {"file_editor", "str_replace_editor"}
_PLAN_TOOLS = {"task_tracker"}
_FILE_MUTATIONS = {"create", "write", "str_replace", "insert", "undo_edit"}

# Frontend enums -----------------------------------------------------------
_PLAN_STEP_STATUS = {"pending", "running", "completed", "failed", "skipped"}
_PLAN_STATUS_MAP = {
    # Map task_tracker's status vocabulary to Forge-OH PlanStepStatusSchema.
    "todo": "pending",
    "in_progress": "running",
    "in-progress": "running",
    "doing": "running",
    "done": "completed",
    "completed": "completed",
    "cancelled": "skipped",
    "canceled": "skipped",
    "skipped": "skipped",
    "failed": "failed",
    "error": "failed",
}


def _pair_observations(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return {action_id: observation_event} for O(1) pairing."""
    pairs: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("kind") != "ObservationEvent":
            continue
        aid = e.get("action_id")
        if aid:
            pairs[aid] = e
    return pairs


def _duration_ms(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        # Timestamps are ISO 8601 strings like "2026-08-02T23:23:49.746571".
        from datetime import datetime

        s = datetime.fromisoformat(start.rstrip("Z"))
        e = datetime.fromisoformat(end.rstrip("Z"))
        return max(0, int((e - s).total_seconds() * 1000))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _extract_command_str(action: dict[str, Any]) -> str:
    """Best-effort extract of the shell command string from an action payload."""
    if not isinstance(action, dict):
        return ""
    # OpenHands ActionEvent.action.command is the canonical field.
    cmd = action.get("command")
    if isinstance(cmd, str):
        return cmd
    # Fallback for tool_call.arguments JSON string.
    args = action.get("arguments")
    if isinstance(args, dict) and isinstance(args.get("command"), str):
        return args["command"]
    return ""


def _extract_observation_output(obs: dict[str, Any] | None) -> tuple[str, int | None]:
    if not obs:
        return "", None
    o = obs.get("observation") or {}
    if isinstance(o, dict):
        output = o.get("output") or o.get("content") or ""
        exit_code = o.get("exit_code")
        if isinstance(exit_code, str) and exit_code.isdigit():
            exit_code = int(exit_code)
        return (output if isinstance(output, str) else str(output)), (
            exit_code if isinstance(exit_code, int) else None
        )
    # Some observations carry output at top-level.
    output = obs.get("output") or ""
    exit_code = obs.get("exit_code")
    return (output if isinstance(output, str) else str(output)), (
        exit_code if isinstance(exit_code, int) else None
    )


def build_commands(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return TerminalCommand[] matching src/lib/schemas/terminal.ts."""
    obs_by_action = _pair_observations(events)
    out: list[dict[str, Any]] = []
    for e in events:
        if e.get("kind") != "ActionEvent":
            continue
        tool = (e.get("tool_name") or "").lower()
        if tool not in _BASH_TOOLS:
            continue
        action = e.get("action") or {}
        obs = obs_by_action.get(e.get("id") or "")
        output, exit_code = _extract_observation_output(obs)
        out.append(
            {
                "id": e.get("id") or "",
                "command": _extract_command_str(action),
                "output": output,
                "exitCode": exit_code,
                "startedAt": e.get("timestamp") or "",
                "durationMs": _duration_ms(e.get("timestamp"), (obs or {}).get("timestamp")),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def _looks_binary(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".bz2",
        ".xz",
        ".mp3",
        ".mp4",
        ".wav",
        ".ogg",
        ".mov",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".class",
        ".pyc",
    }


def build_artifacts(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """Return Artifact[] matching src/lib/schemas/artifact.ts.

    Each file_editor mutating action == one artifact of type file_change.
    Same path edited multiple times produces multiple artifacts (history).
    """
    out: list[dict[str, Any]] = []
    for e in events:
        if e.get("kind") != "ActionEvent":
            continue
        tool = (e.get("tool_name") or "").lower()
        if tool not in _FILE_TOOLS:
            continue
        action = e.get("action") or {}
        cmd = (action.get("command") or "").lower()
        if cmd not in _FILE_MUTATIONS:
            continue
        path = action.get("path") or ""
        if not isinstance(path, str) or not path:
            continue
        # Sanitize the "path</path>..." mangling we see in older ActionEvents.
        if "</path>" in path:
            path = path.split("</path>", 1)[0]
        name = os.path.basename(path) or path
        out.append(
            {
                "id": e.get("id") or "",
                "runId": run_id,
                "type": "file_change",
                "name": name,
                "path": path,
                "createdAt": e.get("timestamp") or "",
                "isBinary": _looks_binary(path),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _normalize_plan_status(raw: Any) -> str:
    if isinstance(raw, str):
        low = raw.lower().replace(" ", "_")
        if low in _PLAN_STEP_STATUS:
            return low
        if low in _PLAN_STATUS_MAP:
            return _PLAN_STATUS_MAP[low]
    return "pending"


def _extract_plan_steps(observation_content: Any) -> list[dict[str, Any]]:
    """Extract task list from a task_tracker ObservationEvent.observation.

    task_tracker observations carry the current task list. The shape varies
    across upstream versions; we tolerate:
        {"tasks": [{"id","title","status"}, ...]}
        {"items": [...]}
        [{"id","title","status"}, ...]
    """
    tasks = None
    if isinstance(observation_content, dict):
        tasks = observation_content.get("tasks") or observation_content.get("items")
    elif isinstance(observation_content, list):
        tasks = observation_content
    if not isinstance(tasks, list):
        return []
    steps: list[dict[str, Any]] = []
    for idx, t in enumerate(tasks):
        if not isinstance(t, dict):
            continue
        title = t.get("title") or t.get("label") or t.get("description") or t.get("text")
        if not title:
            continue
        steps.append(
            {
                "id": str(t.get("id") or f"step-{idx}"),
                "title": str(title),
                "label": str(title),
                "status": _normalize_plan_status(t.get("status")),
                "order": _order if isinstance((_order := t.get("order")), int) else idx,
            }
        )
    return steps


def build_plan(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """Return PlanNode[] matching src/lib/schemas/plan.ts.

    We use the LATEST task_tracker observation as the current plan state
    (task_tracker rewrites the full list on each call).
    """
    obs_by_action = _pair_observations(events)
    latest_steps: list[dict[str, Any]] = []
    latest_ts: str = ""
    for e in events:
        if e.get("kind") != "ActionEvent":
            continue
        tool = (e.get("tool_name") or "").lower()
        if tool not in _PLAN_TOOLS:
            continue
        obs = obs_by_action.get(e.get("id") or "")
        if not obs:
            continue
        observation = obs.get("observation") or obs.get("content") or {}
        steps = _extract_plan_steps(observation)
        ts = obs.get("timestamp") or e.get("timestamp") or ""
        if steps and ts >= latest_ts:
            latest_steps = steps
            latest_ts = ts
    # Attach planId to each step.
    plan_id = f"plan-{run_id}"
    for s in latest_steps:
        s["planId"] = plan_id
    return latest_steps


# ---------------------------------------------------------------------------
# Browser frames — reconstruct BrowserFrame[] matching
# src/lib/schemas/browser.ts from agent-server ActionEvents whose tool is
# 'browser'. Screenshot URLs are proxied back through the BFF once the
# agent-server exposes them; for now we emit whatever URLs (if any) the
# tool observation carries.
# ---------------------------------------------------------------------------

_BROWSER_TOOLS = {"browser", "browse", "browsing", "browser_tool", "browser_tool_set"}


def build_browser_frames(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """Return BrowserFrame[] matching src/lib/schemas/browser.ts.

    One frame per browser ActionEvent, paired with its observation if available.
    Empty list if the run made no browser calls.
    """
    obs_by_action = _pair_observations(events)
    frames: list[dict[str, Any]] = []
    seq = 0
    for e in events:
        if e.get("kind") != "ActionEvent":
            continue
        tool = (e.get("tool_name") or "").lower()
        if tool not in _BROWSER_TOOLS:
            continue
        action_args = e.get("action") or e.get("arguments") or {}
        obs = obs_by_action.get(e.get("id") or "") or {}
        observation = obs.get("observation") or obs.get("content") or {}
        frames.append(
            {
                "id": e.get("id") or f"browser-{run_id}-{seq}",
                "runId": run_id,
                "timestamp": e.get("timestamp") or obs.get("timestamp") or "",
                "seq": seq,
                "url": observation.get("url") or action_args.get("url"),
                "screenshotUrl": observation.get("screenshot_url")
                or observation.get("screenshotUrl"),
                "domSnapshotUrl": observation.get("dom_snapshot_url"),
                "action": action_args.get("action_type") or action_args.get("type") or "navigate",
                "selector": action_args.get("selector"),
                "error": observation.get("error"),
            }
        )
        seq += 1
    return frames
