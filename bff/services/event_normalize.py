"""
event_normalize.py — Project raw agent-server events to the shape the
Next.js EventCard consumes: {id, type, timestamp, source, summary, raw}.

The agent-server emits richly-typed events (MessageEvent, ActionEvent,
ObservationEvent, AgentErrorEvent, …). The frontend `ToolEventSchema`
expects a lowercased `type` and a rendered `summary` string. This
module keeps the projection in one place so every endpoint that returns
events (GET /runs/{id}/events, SSE relay) can call it.

Do NOT drop unrecognized fields — pass them through in `raw` so the
event-detail drawer keeps working.
"""

from __future__ import annotations

from typing import Any


_KIND_TO_TYPE: dict[str, str] = {
    "MessageEvent":                "message",
    "ActionEvent":                 "action",
    "ObservationEvent":            "observation",
    "AgentErrorEvent":             "error",
    "ConversationErrorEvent":      "error",
    "ConversationStateUpdateEvent":"status",
    "CondensationSummaryEvent":    "status",
    "LLMCompletionLogEvent":       "status",
    "PauseEvent":                  "run_paused",
    "SystemPromptEvent":           "status",
    "TokenEvent":                  "status",
}


def _message_summary(ev: dict[str, Any]) -> str:
    """Extract user-visible text from a MessageEvent."""
    llm_message = ev.get("llm_message") or {}
    content = llm_message.get("content") or []
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        # TextContent → {"type": "text", "text": "..."}
        if item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
        # ImageContent → hint at attachment
        elif item.get("type") in {"image", "image_url"}:
            parts.append("[image]")
    if parts:
        return "\n".join(parts).strip()
    # Fallback to tool_call summary
    tool_calls = llm_message.get("tool_calls") or []
    if tool_calls:
        names = [tc.get("name") for tc in tool_calls if isinstance(tc, dict) and tc.get("name")]
        if names:
            return "→ " + ", ".join(names)
    return llm_message.get("role") or ""


def _action_summary(ev: dict[str, Any]) -> str:
    """ActionEvent already has its own top-level `summary`; fall back to thought."""
    if ev.get("summary"):
        return str(ev["summary"])
    if ev.get("thought"):
        return str(ev["thought"])
    tool = ev.get("tool_name") or ""
    action = ev.get("action") or {}
    if isinstance(action, dict):
        # Common shapes: {"command": "..."} for bash, {"path": "..."} for file_editor
        cmd = action.get("command") or action.get("path") or action.get("query")
        if cmd:
            return f"{tool}: {cmd}" if tool else str(cmd)
    return tool or "action"


def _observation_summary(ev: dict[str, Any]) -> str:
    """ObservationEvent — surface either agent-set summary or first text chunk."""
    if ev.get("summary"):
        return str(ev["summary"])
    obs = ev.get("observation") or {}
    if isinstance(obs, dict):
        for k in ("content", "output", "text", "result"):
            v = obs.get(k)
            if isinstance(v, str) and v.strip():
                # Truncate very long tool outputs to keep the timeline scannable
                return v.strip()[:400]
    return "observation"


def _error_summary(ev: dict[str, Any]) -> str:
    for k in ("summary", "message", "error", "detail"):
        v = ev.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "error"


def _generic_summary(ev: dict[str, Any]) -> str:
    for k in ("summary", "message", "status", "description"):
        v = ev.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ev.get("kind", "event")


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Project a raw agent-server event to the frontend ToolEvent shape."""
    if not isinstance(raw, dict):
        return {
            "id": "",
            "type": "unknown",
            "timestamp": "",
            "summary": "",
            "raw": raw,
        }

    kind = raw.get("kind") or ""
    typ = _KIND_TO_TYPE.get(kind, kind.lower() if kind else "event")

    if kind == "MessageEvent":
        summary = _message_summary(raw)
    elif kind == "ActionEvent":
        summary = _action_summary(raw)
    elif kind == "ObservationEvent":
        summary = _observation_summary(raw)
    elif kind in {"AgentErrorEvent", "ConversationErrorEvent"}:
        summary = _error_summary(raw)
    else:
        summary = _generic_summary(raw)

    return {
        "id":         raw.get("id") or "",
        "eventId":    raw.get("id") or "",
        "type":       typ,
        "timestamp":  raw.get("timestamp") or "",
        "source":     raw.get("source"),
        "summary":    summary,
        "raw":        raw,
    }


def normalize_events(items: list[Any]) -> list[dict[str, Any]]:
    return [normalize_event(x) for x in items if isinstance(x, dict)]
