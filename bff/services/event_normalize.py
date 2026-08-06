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
    "MessageEvent": "message",
    "ActionEvent": "action",
    "ObservationEvent": "observation",
    "AgentErrorEvent": "error",
    "ConversationErrorEvent": "error",
    "ConversationStateUpdateEvent": "status",
    "CondensationSummaryEvent": "status",
    "LLMCompletionLogEvent": "status",
    "PauseEvent": "run_paused",
    "SystemPromptEvent": "status",
    "TokenEvent": "status",
}


def _extract_text_from_content(content: Any) -> list[str]:
    """Best-effort extraction of user-visible text from a `content` field.

    Handles all shapes we've seen from the agent-server:
      - str                             → [str]
      - list[str]                       → the list
      - list[TextContent-dict]          → texts
      - list[dict with 'content' key]   → recurse
      - None / anything else            → []
    """
    if content is None:
        return []
    if isinstance(content, str):
        s = content.strip()
        return [s] if s else []
    if not isinstance(content, list):
        return []
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            s = item.strip()
            if s:
                parts.append(s)
        elif isinstance(item, dict):
            typ = item.get("type")
            # TextContent → {"type": "text", "text": "..."}
            if typ == "text":
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
            elif typ in {"image", "image_url"}:
                parts.append("[image]")
            else:
                # Some serializations put the text under "content" or "value"
                for key in ("text", "content", "value", "body"):
                    v = item.get(key)
                    if isinstance(v, str) and v.strip():
                        parts.append(v.strip())
                        break
    return parts


def _message_summary(ev: dict[str, Any]) -> str:
    """Extract user-visible text from a MessageEvent.

    Tries multiple field paths because the agent-server persists MessageEvents
    in slightly different shapes depending on source (user vs assistant vs
    replayed history).
    """
    # 1. Standard SDK shape: ev.llm_message.content
    llm_message = ev.get("llm_message") or ev.get("message") or {}
    if not isinstance(llm_message, dict):
        llm_message = {}

    parts = _extract_text_from_content(llm_message.get("content"))
    if parts:
        return "\n".join(parts).strip()

    # 2. Some older shapes place content at ev.content directly
    parts = _extract_text_from_content(ev.get("content"))
    if parts:
        return "\n".join(parts).strip()

    # 3. Tool-call fallback (agent turned in tools without free text)
    tool_calls = llm_message.get("tool_calls") or ev.get("tool_calls") or []
    if isinstance(tool_calls, list) and tool_calls:
        names: list[str] = [
            str(tc.get("name")) for tc in tool_calls if isinstance(tc, dict) and tc.get("name")
        ]
        if names:
            return "→ " + ", ".join(names)

    # 4. Reasoning-only assistant turn — surface a hint from reasoning_content
    rc = llm_message.get("reasoning_content")
    if isinstance(rc, str) and rc.strip():
        return rc.strip()[:200]

    # 5. Activated skills (agent context turn)
    skills = ev.get("activated_skills") or []
    if isinstance(skills, list) and skills:
        return "activated: " + ", ".join(str(s) for s in skills[:3])

    # 6. Final fallback — role label so the row is never fully blank
    role = llm_message.get("role") or ev.get("source")
    if role:
        return f"({role} message)"
    return "(message)"


# Stage 4.4 — Serena LSP tool names (upstream oraios/serena main).
# When an ActionEvent's `tool_name` is one of these, we rewrite the event's
# `type` to `lsp_<op>` so the frontend can render it with an LSP-specific
# icon and label. Discriminator lives on the flat `type` string — no new
# discriminated union (see ADR-018).
_SERENA_TOOL_TO_LSP_OP: dict[str, str] = {
    # Structural read
    "find_symbol": "find_symbol",
    "find_referencing_symbols": "find_referencing_symbols",
    "find_implementations": "find_implementations",
    "find_declaration": "find_declaration",
    "get_symbols_overview": "get_symbols_overview",
    "get_diagnostics_for_file": "get_diagnostics",
    # Structural write
    "replace_symbol_body": "replace_symbol_body",
    "insert_after_symbol": "insert_after_symbol",
    "insert_before_symbol": "insert_before_symbol",
    "rename_symbol": "rename_symbol",
    "safe_delete_symbol": "safe_delete_symbol",
}


def _serena_op_from_tool_name(tool_name: str) -> str | None:
    """Return the canonical LSP op name if `tool_name` is a known Serena tool.

    Matches on the last dotted segment so both bare (`find_symbol`) and
    namespaced (`serena.find_symbol`, `mcp.serena.find_symbol`) shapes work.
    """
    if not tool_name:
        return None
    tail = tool_name.rsplit(".", 1)[-1]
    return _SERENA_TOOL_TO_LSP_OP.get(tail)


def _action_summary(ev: dict[str, Any]) -> str:
    """ActionEvent already has its own top-level `summary`; fall back to thought."""
    # Explicit agent-set summary always wins — including for Serena tools.
    if ev.get("summary"):
        return str(ev["summary"])

    tool = ev.get("tool_name") or ""
    action = ev.get("action") or {}

    # Stage 4.4: for Serena LSP tools without an explicit summary, produce
    # a compact `Serena <op>: <symbol>` line so the timeline reads
    # symbol-precise at a glance.
    op = _serena_op_from_tool_name(tool)
    if op:
        symbol = None
        if isinstance(action, dict):
            symbol = (
                action.get("name_path")
                or action.get("symbol")
                or action.get("name")
                or action.get("query")
            )
        prefix = f"Serena {op}"
        return f"{prefix}: {symbol}" if symbol else prefix

    if ev.get("thought"):
        return str(ev["thought"])
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


# Valid SecurityRisk enum values from openhands.sdk.security.risk (SDK 1.40.0).
# We pass these through verbatim to the frontend; anything else is dropped.
_VALID_SECURITY_RISK = {"UNKNOWN", "LOW", "MEDIUM", "HIGH"}


def _extract_security_risk(raw: dict[str, Any]) -> str | None:
    """Pull `security_risk` off an ActionEvent, normalized to an enum string.

    Returns None when the field is absent or invalid. Populated only when a
    SecurityAnalyzer is attached to the conversation (Stage 3.1 attaches
    PatternSecurityAnalyzer by default; see BUILD_LOG.md).
    """
    v = raw.get("security_risk")
    if v is None:
        return None
    # SDK may serialize as an enum member or its string value.
    if hasattr(v, "value"):
        v = v.value
    if isinstance(v, str) and v in _VALID_SECURITY_RISK:
        return v
    return None


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
        # Stage 4.4: if this ActionEvent invoked a Serena tool, promote the
        # event's `type` from generic "action" to `lsp_<op>` so the frontend
        # EventCard can render an LSP-specific icon and label.
        _lsp_op = _serena_op_from_tool_name(raw.get("tool_name") or "")
        if _lsp_op:
            typ = f"lsp_{_lsp_op}"
    elif kind == "ObservationEvent":
        summary = _observation_summary(raw)
    elif kind in {"AgentErrorEvent", "ConversationErrorEvent"}:
        summary = _error_summary(raw)
    else:
        summary = _generic_summary(raw)

    out: dict[str, Any] = {
        "id": raw.get("id") or "",
        "eventId": raw.get("id") or "",
        "type": typ,
        "timestamp": raw.get("timestamp") or "",
        "source": raw.get("source"),
        "summary": summary,
        "raw": raw,
    }

    # Stage 3.1: surface SecurityAnalyzer risk annotations on ActionEvents.
    # Only add the key when the value is a known SecurityRisk enum member;
    # frontend hides the badge on UNKNOWN/absent.
    if kind == "ActionEvent":
        risk = _extract_security_risk(raw)
        if risk is not None:
            out["securityRisk"] = risk

    return out


def normalize_events(items: list[Any]) -> list[dict[str, Any]]:
    return [normalize_event(x) for x in items if isinstance(x, dict)]
