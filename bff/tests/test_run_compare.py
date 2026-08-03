"""Tests for bff.services.run_compare."""
from __future__ import annotations

import tempfile
from pathlib import Path

from bff.services.run_compare import compare_runs, _diff_counts, _language_for


# --- event factory helpers ---------------------------------------------------

def _action(idx: int, path: str, tool: str = "file_editor", command: str = "create") -> dict:
    return {
        "id": f"act-{idx}",
        "kind": "ActionEvent",
        "tool_name": tool,
        "action": {"command": command, "path": path, "file_text": "content"},
        "timestamp": f"2026-08-03T00:00:{idx:02d}",
    }


def _obs(idx: int, action_id: str) -> dict:
    return {
        "id": f"obs-{idx}",
        "kind": "ObservationEvent",
        "action_id": action_id,
        "observation": {"content": "ok"},
        "timestamp": f"2026-08-03T00:00:{idx:02d}.5",
    }


# --- tests -------------------------------------------------------------------

def test_compare_no_files_touched():
    result = compare_runs("base-id", "fork-id", [], [], None, None)
    assert result["baseRunId"] == "base-id"
    assert result["forkRunId"] == "fork-id"
    assert result["files"] == []
    assert result["stats"] == {"totalFiles": 0, "additions": 0, "deletions": 0}


def test_compare_same_path_touched_by_both_is_modified():
    base = [_action(1, "/workspace/foo.txt"), _obs(1, "act-1")]
    fork = [_action(1, "/workspace/foo.txt"), _obs(1, "act-1")]
    result = compare_runs("b", "f", base, fork, None, None)
    assert len(result["files"]) == 1
    assert result["files"][0]["path"] == "/workspace/foo.txt"
    assert result["files"][0]["status"] == "modified"


def test_compare_path_only_in_fork_is_added():
    fork = [_action(1, "/workspace/new.txt"), _obs(1, "act-1")]
    result = compare_runs("b", "f", [], fork, None, None)
    assert result["files"][0]["status"] == "added"


def test_compare_path_only_in_base_is_deleted():
    base = [_action(1, "/workspace/gone.txt"), _obs(1, "act-1")]
    result = compare_runs("b", "f", base, [], None, None)
    assert result["files"][0]["status"] == "deleted"


def test_compare_content_diff_when_both_files_readable(tmp_path: Path):
    base_dir = tmp_path / "base"
    fork_dir = tmp_path / "fork"
    base_dir.mkdir()
    fork_dir.mkdir()
    (base_dir / "foo.txt").write_text("line1\nline2\nline3\n")
    (fork_dir / "foo.txt").write_text("line1\nline2 changed\nline3\nline4\n")

    events = [_action(1, "/workspace/foo.txt"), _obs(1, "act-1")]
    result = compare_runs("b", "f", events, events, str(base_dir), str(fork_dir))
    file = result["files"][0]
    assert file["original"] == "line1\nline2\nline3\n"
    assert file["modified"] == "line1\nline2 changed\nline3\nline4\n"
    assert file["additions"] == 2  # "line2 changed" and "line4"
    assert file["deletions"] == 1  # "line2"
    assert result["stats"]["additions"] == 2
    assert result["stats"]["deletions"] == 1


def test_compare_binary_extension_skips_content_read(tmp_path: Path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "img.png").write_bytes(b"\x89PNG fake bytes")

    events = [_action(1, "/workspace/img.png"), _obs(1, "act-1")]
    result = compare_runs("b", "f", events, [], str(base_dir), None)
    file = result["files"][0]
    assert file["isBinary"] is True
    assert file["original"] is None
    assert file["additions"] == 0
    assert file["deletions"] == 0


def test_compare_missing_workspace_returns_null_content():
    events = [_action(1, "/workspace/foo.txt"), _obs(1, "act-1")]
    result = compare_runs("b", "f", events, events, None, None)
    file = result["files"][0]
    assert file["original"] is None
    assert file["modified"] is None
    assert file["additions"] == 0
    assert file["deletions"] == 0
    assert file["status"] == "modified"


def test_language_detection_python():
    assert _language_for("/workspace/foo.py") == "python"
    assert _language_for("/workspace/foo.ts") == "typescript"
    assert _language_for("/workspace/foo.unknown") == "plaintext"


def test_diff_counts_pure_addition():
    add, dele = _diff_counts("", "a\nb\nc\n")
    assert add == 3
    assert dele == 0


def test_diff_counts_pure_deletion():
    add, dele = _diff_counts("a\nb\nc\n", "")
    assert add == 0
    assert dele == 3
