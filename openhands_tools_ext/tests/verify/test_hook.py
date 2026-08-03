"""Tests for the STOP-hook CLI shim."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from openhands_tools_ext.verify import hook as hook_mod


def _stdin(monkeypatch: pytest.MonkeyPatch, payload: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))


def _stdout(capsys: pytest.CaptureFixture[str]) -> str:
    return capsys.readouterr().out


def test_empty_stdin_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stdin(monkeypatch, "")
    assert hook_mod.main() == 1
    assert "empty stdin" in capsys.readouterr().err


def test_bad_json_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stdin(monkeypatch, "not json {{{")
    assert hook_mod.main() == 1
    assert "bad JSON" in capsys.readouterr().err


def test_non_stop_event_is_noop(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stdin(monkeypatch, json.dumps({"event_type": "PreToolUse"}))
    assert hook_mod.main() == 0
    body = json.loads(_stdout(capsys))
    assert "non-STOP" in body["reason"]


def test_missing_project_dir_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stdin(monkeypatch, json.dumps({"event_type": "Stop"}))
    monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
    monkeypatch.delenv("OPENHANDS_WORKING_DIR", raising=False)
    assert hook_mod.main() == 1


def test_stop_event_persists_state_across_invocations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Workspace with no runner — every attempt will SKIP but the
    # iteration counter should still not fire because SKIPPED does not
    # consume an attempt (verify: the loop increments _iterations_used
    # before running, so it *does* consume; we assert that behaviour).
    (tmp_path / "note.md").write_text("x")
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("OPENHANDS_SESSION_ID", "sess-1")
    monkeypatch.setenv("FORGE_OH_VERIFY_MAX_ITERATIONS", "2")
    event = json.dumps({"event_type": "Stop", "session_id": "sess-1"})

    _stdin(monkeypatch, event)
    assert hook_mod.main() == 0
    first = json.loads(_stdout(capsys))
    assert "decision" not in first  # SKIPPED verdict → allow stop

    state_file = tmp_path / ".forge-oh" / "verify-state.json"
    assert state_file.is_file()
    saved = json.loads(state_file.read_text())
    assert saved["sess-1"]["iterations_used"] == 1


def test_stop_event_pass_returns_no_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Build a passing pytest workspace.
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')
    (tmp_path / "mymod.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "conftest.py").write_text(
        "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\n"
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mymod.py").write_text(
        "from mymod import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("OPENHANDS_SESSION_ID", "sess-pass")

    event = json.dumps(
        {
            "event_type": "Stop",
            "session_id": "sess-pass",
            "metadata": {"edited_files": [str(tmp_path / "mymod.py")]},
        }
    )
    _stdin(monkeypatch, event)
    assert hook_mod.main() == 0
    body = json.loads(_stdout(capsys))
    assert "decision" not in body  # pass → allow stop
    assert body["additionalContext"]["verdict"] == "pass"


def test_stop_event_fail_returns_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')
    (tmp_path / "mymod.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "conftest.py").write_text(
        "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\n"
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mymod.py").write_text(
        "from mymod import add\n\ndef test_add():\n    assert add(2, 3) == 999\n"
    )
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("OPENHANDS_SESSION_ID", "sess-fail")

    event = json.dumps(
        {
            "event_type": "Stop",
            "session_id": "sess-fail",
            "metadata": {"edited_files": [str(tmp_path / "mymod.py")]},
        }
    )
    _stdin(monkeypatch, event)
    assert hook_mod.main() == 0
    body = json.loads(_stdout(capsys))
    assert body["decision"] == "block"
    assert body["additionalContext"]["verdict"] == "fail"
