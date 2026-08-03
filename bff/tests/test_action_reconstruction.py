"""Unit tests for bff.services.action_reconstruction."""
from __future__ import annotations

from bff.services.action_reconstruction import (
    build_artifacts,
    build_commands,
    build_plan,
)


def _action(*, action_id: str, tool: str, action: dict, timestamp: str):
    return {
        "id": action_id,
        "kind": "ActionEvent",
        "source": "agent",
        "timestamp": timestamp,
        "tool_name": tool,
        "action": action,
    }


def _observation(*, obs_id: str, action_id: str, observation: dict, timestamp: str):
    return {
        "id": obs_id,
        "kind": "ObservationEvent",
        "source": "environment",
        "timestamp": timestamp,
        "action_id": action_id,
        "observation": observation,
    }


# --------------------------------------------------------------------------
# build_commands
# --------------------------------------------------------------------------

def test_build_commands_pairs_action_with_observation():
    events = [
        _action(
            action_id="a1",
            tool="execute_bash",
            action={"command": "ls /tmp", "kind": "BashAction"},
            timestamp="2026-08-03T00:00:00.000000",
        ),
        _observation(
            obs_id="o1",
            action_id="a1",
            observation={"output": "foo\nbar", "exit_code": 0, "kind": "BashObservation"},
            timestamp="2026-08-03T00:00:00.500000",
        ),
    ]
    out = build_commands(events)
    assert len(out) == 1
    cmd = out[0]
    assert cmd["id"] == "a1"
    assert cmd["command"] == "ls /tmp"
    assert cmd["output"] == "foo\nbar"
    assert cmd["exitCode"] == 0
    assert cmd["durationMs"] == 500


def test_build_commands_ignores_non_bash_tools():
    events = [
        _action(
            action_id="a1",
            tool="file_editor",
            action={"command": "create", "path": "/tmp/x"},
            timestamp="t",
        ),
    ]
    assert build_commands(events) == []


def test_build_commands_handles_missing_observation():
    events = [
        _action(
            action_id="a1",
            tool="terminal",
            action={"command": "sleep 5"},
            timestamp="2026-08-03T00:00:00",
        )
    ]
    out = build_commands(events)
    assert len(out) == 1
    assert out[0]["output"] == ""
    assert out[0]["exitCode"] is None
    assert out[0]["durationMs"] is None


# --------------------------------------------------------------------------
# build_artifacts
# --------------------------------------------------------------------------

def test_build_artifacts_captures_file_editor_mutations():
    events = [
        _action(
            action_id="a1",
            tool="file_editor",
            action={"command": "create", "path": "/workspace/foo.txt", "kind": "FileEditorAction"},
            timestamp="2026-08-03T00:00:01",
        ),
        _action(
            action_id="a2",
            tool="file_editor",
            action={"command": "str_replace", "path": "/workspace/foo.txt"},
            timestamp="2026-08-03T00:00:02",
        ),
        _action(
            action_id="a3",
            tool="file_editor",
            action={"command": "view", "path": "/workspace/foo.txt"},
            timestamp="2026-08-03T00:00:03",
        ),
    ]
    arts = build_artifacts(events, "run-xyz")
    assert [a["id"] for a in arts] == ["a1", "a2"]  # 'view' ignored
    assert arts[0]["runId"] == "run-xyz"
    assert arts[0]["type"] == "file_change"
    assert arts[0]["name"] == "foo.txt"
    assert arts[0]["path"] == "/workspace/foo.txt"
    assert arts[0]["isBinary"] is False


def test_build_artifacts_flags_binary_paths():
    events = [
        _action(
            action_id="a1",
            tool="file_editor",
            action={"command": "create", "path": "/workspace/logo.png"},
            timestamp="t",
        )
    ]
    arts = build_artifacts(events, "r")
    assert arts[0]["isBinary"] is True


def test_build_artifacts_handles_legacy_path_mangling():
    # Some early ActionEvents show 'path</path>\n...' contamination.
    events = [
        _action(
            action_id="a1",
            tool="file_editor",
            action={
                "command": "create",
                "path": "/workspace/legacy.txt</path>\n<parameter=file_text>hi",
            },
            timestamp="t",
        )
    ]
    arts = build_artifacts(events, "r")
    assert arts[0]["path"] == "/workspace/legacy.txt"


# --------------------------------------------------------------------------
# build_plan
# --------------------------------------------------------------------------

def test_build_plan_returns_latest_task_tracker_state():
    events = [
        _action(
            action_id="a1",
            tool="task_tracker",
            action={"command": "set_tasks"},
            timestamp="2026-08-03T00:00:01",
        ),
        _observation(
            obs_id="o1",
            action_id="a1",
            observation={
                "tasks": [
                    {"id": "t1", "title": "First", "status": "todo"},
                    {"id": "t2", "title": "Second", "status": "todo"},
                ]
            },
            timestamp="2026-08-03T00:00:01",
        ),
        _action(
            action_id="a2",
            tool="task_tracker",
            action={"command": "update"},
            timestamp="2026-08-03T00:01:00",
        ),
        _observation(
            obs_id="o2",
            action_id="a2",
            observation={
                "tasks": [
                    {"id": "t1", "title": "First", "status": "done"},
                    {"id": "t2", "title": "Second", "status": "in_progress"},
                ]
            },
            timestamp="2026-08-03T00:01:00",
        ),
    ]
    steps = build_plan(events, "run-1")
    assert [s["id"] for s in steps] == ["t1", "t2"]
    assert steps[0]["status"] == "completed"
    assert steps[1]["status"] == "running"
    assert all(s["planId"] == "plan-run-1" for s in steps)


def test_build_plan_empty_when_no_task_tracker():
    events = [
        _action(
            action_id="a1",
            tool="execute_bash",
            action={"command": "ls"},
            timestamp="t",
        )
    ]
    assert build_plan(events, "r") == []


def test_build_plan_tolerates_list_shaped_observation():
    events = [
        _action(
            action_id="a1",
            tool="task_tracker",
            action={},
            timestamp="t",
        ),
        _observation(
            obs_id="o1",
            action_id="a1",
            observation=[
                {"id": "x", "title": "Only step", "status": "pending"},
            ],
            timestamp="t",
        ),
    ]
    steps = build_plan(events, "r")
    assert len(steps) == 1
    assert steps[0]["title"] == "Only step"
