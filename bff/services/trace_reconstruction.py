"""Reconstruct traces/spans on demand from the agent-server event stream.

Design (Slice 7F, Option A):
- Trace = conversation. trace_id == run_id (conversation UUID).
- Spans are derived per-request from events; no persistent SQLite store.
- Two span sources:
    1. ActionEvent  ➜ ObservationEvent (matched by action_id): tool span
    2. MessageEvent (source='agent') between one user message and the next:
       aggregate as an 'llm' span that spans the model turn.

Frontend contract (src/lib/schemas/trace.ts):
    TraceSpan = {
      spanId, traceId, parentSpanId | null,
      name, kind: 'llm'|'tool'|'workspace'|'browser'|'network'|'internal',
      startTime, endTime | null, durationMs | null,
      status: 'ok'|'error'|'unset',
      attributes?, events?, runId?, inputTokens?, outputTokens?,
      estimatedCostUsd?
    }
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Tool → kind mapping. Anything not listed maps to 'tool'.
# ---------------------------------------------------------------------------
_KIND_MAP: dict[str, str] = {
    "execute_bash": "workspace",
    "bash": "workspace",
    "terminal": "workspace",
    "run_bash": "workspace",
    "start_bash_command": "workspace",
    "file_editor": "workspace",
    "str_replace_editor": "workspace",
    "write_file": "workspace",
    "read_file": "workspace",
    "edit": "workspace",
    "list_directory": "workspace",
    "glob": "workspace",
    "grep": "workspace",
    "planning_file_editor": "workspace",
    "task_tracker": "internal",
    "browser_navigate": "browser",
    "browser_click": "browser",
    "browser_type": "browser",
    "browser_scroll": "browser",
    "browser_get_content": "browser",
    "browser_get_state": "browser",
    "browser_tool_set": "browser",
    "browser_go_back": "browser",
    "browser_close_tab": "browser",
    "browser_list_tabs": "browser",
    "browser_switch_tab": "browser",
    "browser_start_recording": "browser",
    "browser_stop_recording": "browser",
    "browser_set_storage": "browser",
    "browser_get_storage": "browser",
    "vision_inspect": "browser",
    "think": "internal",
    "finish": "internal",
    "switch_llm": "internal",
    "workflow": "internal",
    "workflow_tool_set": "internal",
    "task": "internal",
    "task_tool_set": "internal",
    "invoke_skill": "internal",
    # Slice E.1 (Rec #2, verify loop): verify_step spans get their own kind
    # so the Trace tab can render them with a dedicated card component.
    "verify_step": "verify",
}


def _kind_for(tool: str | None) -> str:
    if not tool:
        return "internal"
    if tool.startswith("mcp_"):
        return "network"
    return _KIND_MAP.get(tool, "tool")


def _duration_ms(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        import datetime as dt

        def _parse(s: str) -> dt.datetime:
            s2 = s.replace("Z", "+00:00")
            return dt.datetime.fromisoformat(s2)

        return int((_parse(end) - _parse(start)).total_seconds() * 1000)
    except Exception:
        return None


def _observation_status(observation: Any) -> tuple[str, str | None]:
    """Return (status, error_message)."""
    if not isinstance(observation, dict):
        return ("ok", None)
    ec = observation.get("exit_code")
    if isinstance(ec, int) and ec != 0:
        return ("error", f"exit_code={ec}")
    err = observation.get("error")
    if err:
        return ("error", str(err)[:400])
    is_err = observation.get("is_error") or observation.get("error_kind")
    if is_err:
        return ("error", str(is_err)[:400])
    return ("ok", None)


def _tool_span(
    action: dict[str, Any],
    observation_event: dict[str, Any] | None,
    trace_id: str,
) -> dict[str, Any]:
    action_id = action.get("id") or ""
    tool = action.get("tool_name") or ""
    action_body = action.get("action") or {}
    start = action.get("timestamp")
    end = observation_event.get("timestamp") if observation_event else None
    obs_body = (observation_event or {}).get("observation")
    status, error = _observation_status(obs_body)
    if not observation_event:
        status = "unset"

    attributes: dict[str, Any] = {
        "actionId": action_id,
        "toolName": tool,
    }
    # Surface a few useful action fields when present.
    if isinstance(action_body, dict):
        for key in ("command", "path", "url"):
            if action_body.get(key):
                attributes[key] = action_body[key]

    if error:
        attributes["error"] = error

    return {
        "spanId": action_id,
        "traceId": trace_id,
        "parentSpanId": None,
        "name": tool or "action",
        "kind": _kind_for(tool),
        "startTime": start,
        "endTime": end,
        "durationMs": _duration_ms(start, end),
        "status": status,
        "attributes": attributes,
        "runId": trace_id,
    }


def _extract_llm_usage(msg: dict[str, Any]) -> tuple[int | None, int | None]:
    """Best-effort extraction of {input,output} token usage from a MessageEvent."""
    llm_msg = msg.get("llm_message") or {}
    usage = llm_msg.get("usage") or msg.get("usage") or {}
    if not isinstance(usage, dict):
        return (None, None)
    inp = usage.get("input_tokens") or usage.get("prompt_tokens")
    out = usage.get("output_tokens") or usage.get("completion_tokens")
    return (inp, out)


def build_spans(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """Turn an event stream into a list of TraceSpan dicts.

    Rules:
    - One tool span per ActionEvent (matched with its ObservationEvent).
    - One llm span per agent MessageEvent (represents that agent turn's LLM call).
    """
    # Index observations by action_id
    obs_by_action: dict[str, dict[str, Any]] = {}
    for ev in events:
        if ev.get("kind") == "ObservationEvent":
            aid = ev.get("action_id")
            if aid:
                obs_by_action[aid] = ev

    spans: list[dict[str, Any]] = []

    for ev in events:
        kind = ev.get("kind")

        if kind == "ActionEvent":
            aid = ev.get("id") or ""
            spans.append(_tool_span(ev, obs_by_action.get(aid), run_id))

        elif kind == "MessageEvent":
            source = ev.get("source") or ""
            if source != "agent":
                continue
            ts = ev.get("timestamp")
            inp, out = _extract_llm_usage(ev)
            attrs: dict[str, Any] = {"messageId": ev.get("id")}
            if inp is not None:
                attrs["inputTokens"] = inp
            if out is not None:
                attrs["outputTokens"] = out
            span = {
                "spanId": ev.get("id") or "",
                "traceId": run_id,
                "parentSpanId": None,
                "name": "llm.completion",
                "kind": "llm",
                "startTime": ts,
                "endTime": ts,  # duration unavailable — collapse
                "durationMs": 0,
                "status": "ok",
                "attributes": attrs,
                "runId": run_id,
            }
            if inp is not None:
                span["inputTokens"] = inp
            if out is not None:
                span["outputTokens"] = out
            spans.append(span)

    # Order by startTime (fall back to insertion order for ties/missing)
    spans.sort(key=lambda s: s.get("startTime") or "")
    return spans


def build_trace_summary(spans: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    """Aggregate stats for a trace (single-trace = single-conversation)."""
    if not spans:
        return {
            "traceId": run_id,
            "runId": run_id,
            "spanCount": 0,
            "startTime": None,
            "endTime": None,
            "durationMs": None,
            "status": "unset",
            "errorCount": 0,
            "inputTokens": 0,
            "outputTokens": 0,
        }
    starts = [s["startTime"] for s in spans if s.get("startTime")]
    ends = [s["endTime"] for s in spans if s.get("endTime")]
    start = min(starts) if starts else None
    end = max(ends) if ends else None
    errors = sum(1 for s in spans if s.get("status") == "error")
    inp = sum(s.get("inputTokens") or 0 for s in spans)
    out = sum(s.get("outputTokens") or 0 for s in spans)
    return {
        "traceId": run_id,
        "runId": run_id,
        "spanCount": len(spans),
        "startTime": start,
        "endTime": end,
        "durationMs": _duration_ms(start, end),
        "status": "error" if errors else "ok",
        "errorCount": errors,
        "inputTokens": inp,
        "outputTokens": out,
    }
