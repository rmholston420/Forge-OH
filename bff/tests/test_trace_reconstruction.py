"""Unit tests for bff.services.trace_reconstruction."""
from __future__ import annotations

from bff.services.trace_reconstruction import (
    build_spans,
    build_trace_summary,
)


def _action(*, action_id, tool, action, timestamp):
    return {
        "id": action_id,
        "kind": "ActionEvent",
        "source": "agent",
        "timestamp": timestamp,
        "tool_name": tool,
        "action": action,
    }


def _observation(*, obs_id, action_id, observation, timestamp):
    return {
        "id": obs_id,
        "kind": "ObservationEvent",
        "source": "environment",
        "timestamp": timestamp,
        "action_id": action_id,
        "observation": observation,
    }


def _message(*, msg_id, source, timestamp, usage=None):
    ev = {
        "id": msg_id,
        "kind": "MessageEvent",
        "source": source,
        "timestamp": timestamp,
        "llm_message": {"content": [{"type": "text", "text": "hi"}]},
    }
    if usage:
        ev["llm_message"]["usage"] = usage
    return ev


# ---------------------------------------------------------------------------
# build_spans
# ---------------------------------------------------------------------------

def test_build_spans_pairs_tool_action_and_observation():
    events = [
        _action(
            action_id="a1",
            tool="execute_bash",
            action={"command": "ls /tmp"},
            timestamp="2026-08-03T00:00:00Z",
        ),
        _observation(
            obs_id="o1",
            action_id="a1",
            observation={"output": "ok", "exit_code": 0},
            timestamp="2026-08-03T00:00:00.500Z",
        ),
    ]
    spans = build_spans(events, "run-1")
    assert len(spans) == 1
    s = spans[0]
    assert s["spanId"] == "a1"
    assert s["traceId"] == "run-1"
    assert s["kind"] == "workspace"
    assert s["status"] == "ok"
    assert s["durationMs"] == 500
    assert s["attributes"]["command"] == "ls /tmp"


def test_build_spans_marks_error_on_nonzero_exit_code():
    events = [
        _action(action_id="a1", tool="execute_bash",
                action={"command": "false"}, timestamp="t1"),
        _observation(obs_id="o1", action_id="a1",
                     observation={"output": "", "exit_code": 1}, timestamp="t2"),
    ]
    spans = build_spans(events, "r")
    assert spans[0]["status"] == "error"
    assert "exit_code=1" in spans[0]["attributes"]["error"]


def test_build_spans_unset_status_when_no_observation():
    events = [
        _action(action_id="a1", tool="terminal",
                action={"command": "sleep 60"}, timestamp="t"),
    ]
    spans = build_spans(events, "r")
    assert spans[0]["status"] == "unset"
    assert spans[0]["endTime"] is None
    assert spans[0]["durationMs"] is None


def test_build_spans_llm_span_from_agent_message():
    events = [
        _message(msg_id="m1", source="user", timestamp="2026-08-03T00:00:00Z"),
        _message(
            msg_id="m2",
            source="agent",
            timestamp="2026-08-03T00:00:05Z",
            usage={"input_tokens": 120, "output_tokens": 30},
        ),
    ]
    spans = build_spans(events, "r")
    assert len(spans) == 1
    s = spans[0]
    assert s["kind"] == "llm"
    assert s["name"] == "llm.completion"
    assert s["inputTokens"] == 120
    assert s["outputTokens"] == 30


def test_build_spans_kind_mapping():
    events = [
        _action(action_id="a1", tool="file_editor",
                action={"command": "create", "path": "/tmp/x"}, timestamp="t"),
        _action(action_id="a2", tool="browser_navigate",
                action={"url": "https://example.com"}, timestamp="t"),
        _action(action_id="a3", tool="task_tracker", action={}, timestamp="t"),
        _action(action_id="a4", tool="mcp_test_tool", action={}, timestamp="t"),
    ]
    spans = build_spans(events, "r")
    kinds = {s["spanId"]: s["kind"] for s in spans}
    assert kinds["a1"] == "workspace"
    assert kinds["a2"] == "browser"
    assert kinds["a3"] == "internal"
    assert kinds["a4"] == "network"


def test_build_spans_sorted_by_start_time():
    events = [
        _action(action_id="a2", tool="terminal",
                action={"command": "b"}, timestamp="2026-08-03T00:02:00Z"),
        _action(action_id="a1", tool="terminal",
                action={"command": "a"}, timestamp="2026-08-03T00:01:00Z"),
    ]
    spans = build_spans(events, "r")
    assert [s["spanId"] for s in spans] == ["a1", "a2"]


# ---------------------------------------------------------------------------
# build_trace_summary
# ---------------------------------------------------------------------------

def test_summary_aggregates_status_and_tokens():
    events = [
        _message(msg_id="m1", source="agent",
                 timestamp="2026-08-03T00:00:00Z",
                 usage={"input_tokens": 10, "output_tokens": 5}),
        _action(action_id="a1", tool="execute_bash",
                action={"command": "ls"}, timestamp="2026-08-03T00:00:01Z"),
        _observation(obs_id="o1", action_id="a1",
                     observation={"output": "", "exit_code": 0},
                     timestamp="2026-08-03T00:00:01.100Z"),
    ]
    spans = build_spans(events, "r")
    summary = build_trace_summary(spans, "r")
    assert summary["spanCount"] == 2
    assert summary["errorCount"] == 0
    assert summary["status"] == "ok"
    assert summary["inputTokens"] == 10
    assert summary["outputTokens"] == 5


def test_summary_error_status_when_any_span_failed():
    events = [
        _action(action_id="a1", tool="execute_bash",
                action={"command": "boom"}, timestamp="t"),
        _observation(obs_id="o1", action_id="a1",
                     observation={"exit_code": 2}, timestamp="t"),
    ]
    spans = build_spans(events, "r")
    summary = build_trace_summary(spans, "r")
    assert summary["errorCount"] == 1
    assert summary["status"] == "error"


def test_summary_empty_when_no_events():
    summary = build_trace_summary([], "r")
    assert summary["spanCount"] == 0
    assert summary["status"] == "unset"
