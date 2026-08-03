"""
run_metrics.py — derive per-run KPIs from the agent-server event stream.

Shape returned matches `RunMetricsSchema` in
src/lib/schemas/metric.ts, wrapped as {"data": ...} by the router.

All aggregation is pure Python over the events list; no calls out.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bff.services.action_reconstruction import _pair_observations

_FILE_TOOLS = {"file_editor", "str_replace_editor"}
_FILE_MUTATIONS = {"create", "write", "str_replace", "insert", "undo_edit"}


def _iso_to_ts(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return None


def build_run_metrics(events: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    """Return RunMetrics for the given event list."""
    token_count = 0
    tool_call_count = 0
    cost_usd = 0.0
    touched_paths: set[str] = set()

    first_ts: float | None = None
    last_ts: float | None = None

    for ev in events:
        kind = ev.get("kind") or ""
        ts = _iso_to_ts(ev.get("timestamp"))
        if ts is not None:
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts

        if kind == "ActionEvent":
            tool_call_count += 1
            tool = ev.get("tool_name") or ""
            if tool in _FILE_TOOLS:
                action = ev.get("action") or {}
                if isinstance(action, dict) and action.get("command") in _FILE_MUTATIONS:
                    path = action.get("path") or action.get("file_path")
                    if isinstance(path, str) and path:
                        touched_paths.add(path)

        elif kind == "LLMCompletionLogEvent":
            # Common shapes: usage.total_tokens / usage.prompt_tokens+completion_tokens
            usage = ev.get("usage") or {}
            if isinstance(usage, dict):
                tt = usage.get("total_tokens")
                if isinstance(tt, int | float):
                    token_count += int(tt)
                else:
                    pt = usage.get("prompt_tokens") or 0
                    ct = usage.get("completion_tokens") or 0
                    if isinstance(pt, int | float) and isinstance(ct, int | float):
                        token_count += int(pt) + int(ct)
            cost = ev.get("cost_usd") or ev.get("cost")
            if isinstance(cost, int | float):
                cost_usd += float(cost)

        elif kind == "TokenEvent":
            v = ev.get("token_count") or ev.get("value") or ev.get("total_tokens")
            if isinstance(v, int | float):
                token_count += int(v)

    duration_ms = 0
    if first_ts is not None and last_ts is not None and last_ts > first_ts:
        duration_ms = int((last_ts - first_ts) * 1000)

    return {
        "tokenCount": token_count,
        "toolCallCount": tool_call_count,
        "filesTouchedCount": len(touched_paths),
        "costUsd": round(cost_usd, 6),
        "durationMs": duration_ms,
        "series": [],
    }


# Silence "imported but unused" for future observation-pairing extensions.
_ = _pair_observations
