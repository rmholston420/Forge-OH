"""Tests for VerifyLoop retry policy."""

from __future__ import annotations

import textwrap
from pathlib import Path

from openhands_tools_ext.verify.loop import VerifyLoop
from openhands_tools_ext.verify.schema import VerifyVerdict


def _pytest_workspace(tmp_path: Path, *, will_pass: bool) -> tuple[Path, Path]:
    """Build a real workspace with a pyproject.toml and a passing/failing test."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')
    src = tmp_path / "mymod.py"
    src.write_text("def add(a, b):\n    return a + b\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    # A conftest at the workspace root puts the workspace on sys.path so
    # tests can import the top-level module. This mirrors the standard
    # small-project pytest layout.
    (tmp_path / "conftest.py").write_text(
        "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\n"
    )
    if will_pass:
        (tests_dir / "test_mymod.py").write_text(
            textwrap.dedent(
                """
                from mymod import add

                def test_add():
                    assert add(2, 3) == 5
                """
            ).strip()
        )
    else:
        (tests_dir / "test_mymod.py").write_text(
            textwrap.dedent(
                """
                from mymod import add

                def test_add_broken():
                    assert add(2, 3) == 999
                """
            ).strip()
        )
    return tmp_path, src


class TestVerifyLoopPassPath:
    def test_pass_verdict_allows_stop(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=True)
        loop = VerifyLoop(workspace=workspace, max_iterations=3)
        loop.note_edit(src)
        decision = loop.on_stop()
        assert decision.block is False
        assert decision.step is not None
        assert decision.step.verdict == VerifyVerdict.PASS.value
        assert decision.iteration == 1

    def test_pass_clears_edit_set(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=True)
        loop = VerifyLoop(workspace=workspace, max_iterations=3)
        loop.note_edit(src)
        loop.on_stop()
        assert loop.edited_files_since_last_verify == []


class TestVerifyLoopFailPath:
    def test_fail_within_budget_blocks(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=False)
        loop = VerifyLoop(workspace=workspace, max_iterations=3)
        loop.note_edit(src)
        decision = loop.on_stop()
        assert decision.block is True
        assert decision.step is not None
        assert decision.step.verdict == VerifyVerdict.FAIL.value
        assert decision.iteration == 1

    def test_budget_exhausted_allows_stop_but_records_step(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=False)
        loop = VerifyLoop(workspace=workspace, max_iterations=2)
        loop.note_edit(src)
        # First attempt: blocks.
        first = loop.on_stop()
        assert first.block is True
        # Second attempt (budget cap): allows stop, still records the verdict.
        loop.note_edit(src)  # re-note as if the agent hadn't fixed anything
        second = loop.on_stop()
        assert second.block is False
        assert second.step is not None
        assert second.step.verdict == VerifyVerdict.FAIL.value
        assert second.iteration == 2

    def test_over_cap_returns_no_step(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=False)
        loop = VerifyLoop(workspace=workspace, max_iterations=1)
        loop.note_edit(src)
        first = loop.on_stop()
        assert first.iteration == 1
        # Now cap is reached: no more verification runs.
        third = loop.on_stop()
        assert third.block is False
        assert third.step is None
        assert "cap reached" in third.reason


class TestVerifyLoopSkip:
    def test_no_runner_skips(self, tmp_path: Path) -> None:
        # Workspace with no pyproject / package.json.
        (tmp_path / "note.md").write_text("hello")
        loop = VerifyLoop(workspace=tmp_path, max_iterations=3)
        decision = loop.on_stop()
        assert decision.block is False
        assert decision.step is not None
        assert decision.step.verdict == VerifyVerdict.SKIPPED.value


class TestVerifyLoopNoteEditNormalisation:
    def test_relative_path_resolved_against_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        loop = VerifyLoop(workspace=tmp_path, max_iterations=3)
        loop.note_edit(Path("a.py"))
        assert loop.edited_files_since_last_verify[0].is_absolute()
        assert loop.edited_files_since_last_verify[0].name == "a.py"

    def test_duplicate_edits_deduplicated(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        loop = VerifyLoop(workspace=tmp_path, max_iterations=3)
        loop.note_edit(Path("a.py"))
        loop.note_edit(tmp_path / "a.py")
        assert len(loop.edited_files_since_last_verify) == 1


class TestDecisionSerialisation:
    def test_block_decision_has_decision_key(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=False)
        loop = VerifyLoop(workspace=workspace, max_iterations=3)
        loop.note_edit(src)
        decision = loop.on_stop()
        payload = decision.to_hook_json()
        assert payload.get("decision") == "block"
        assert "reason" in payload
        assert "additionalContext" in payload

    def test_allow_decision_omits_decision_key(self, tmp_path: Path) -> None:
        workspace, src = _pytest_workspace(tmp_path, will_pass=True)
        loop = VerifyLoop(workspace=workspace, max_iterations=3)
        loop.note_edit(src)
        decision = loop.on_stop()
        payload = decision.to_hook_json()
        assert "decision" not in payload
