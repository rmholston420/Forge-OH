"""Tests for the verify runner (subprocess wrapper)."""

from __future__ import annotations

import sys
from pathlib import Path

from openhands_tools_ext.verify.runner import (
    DEFAULT_TIMEOUT_SECONDS,
    run_verification,
)
from openhands_tools_ext.verify.schema import (
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
)
from openhands_tools_ext.verify.selector import RunnerConfig


def _echo_runner(exit_code: int = 0, stderr_msg: str = "") -> RunnerConfig:
    """Build a runner config that shells out to python -c '...'.

    Uses ``sys.executable`` so the tests work in the project's uv venv
    without depending on a specific ``python`` on PATH.
    """
    if stderr_msg:
        code = f"import sys; sys.stderr.write({stderr_msg!r}); sys.exit({exit_code})"
    else:
        code = f"import sys; sys.exit({exit_code})"
    return RunnerConfig(
        runner=VerifyRunner.PYTEST,
        command_prefix=[sys.executable, "-c", code],
    )


class TestRunVerification:
    def test_no_runner_detected_returns_skipped(self, tmp_path: Path) -> None:
        step = run_verification(
            workspace=tmp_path,
            edited_files=[],
            iteration=1,
            max_iterations=3,
        )
        assert isinstance(step, VerificationStep)
        assert step.verdict == VerifyVerdict.SKIPPED
        assert step.runner == VerifyRunner.UNKNOWN
        assert step.exit_code is None
        assert step.duration_ms == 0

    def test_empty_targets_returns_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        # No edited files -> no targets selected.
        step = run_verification(
            workspace=tmp_path,
            edited_files=[],
            iteration=1,
            max_iterations=3,
        )
        assert step.verdict == VerifyVerdict.SKIPPED
        assert step.runner == VerifyRunner.PYTEST
        assert step.test_selected == []

    def test_zero_exit_code_marked_pass(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        (tmp_path / "test_ok.py").write_text("def test_ok(): pass\n")
        step = run_verification(
            workspace=tmp_path,
            edited_files=[tmp_path / "test_ok.py"],
            iteration=1,
            max_iterations=3,
            runner_override=_echo_runner(exit_code=0),
        )
        assert step.verdict == VerifyVerdict.PASS
        assert step.exit_code == 0
        assert step.test_selected == ["test_ok.py"]
        assert step.iteration == 1
        assert step.max_iterations == 3

    def test_nonzero_exit_code_marked_fail(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        (tmp_path / "test_bad.py").write_text("def test_bad(): pass\n")
        step = run_verification(
            workspace=tmp_path,
            edited_files=[tmp_path / "test_bad.py"],
            iteration=2,
            max_iterations=3,
            runner_override=_echo_runner(exit_code=1, stderr_msg="AssertionError: expected 1 == 2"),
        )
        assert step.verdict == VerifyVerdict.FAIL
        assert step.exit_code == 1
        assert "AssertionError" in step.stderr_tail
        assert step.iteration == 2

    def test_missing_runner_binary_marked_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        (tmp_path / "test_ok.py").write_text("def test_ok(): pass\n")
        override = RunnerConfig(
            runner=VerifyRunner.PYTEST,
            command_prefix=["/no/such/binary/pytest-xyzzy"],
        )
        step = run_verification(
            workspace=tmp_path,
            edited_files=[tmp_path / "test_ok.py"],
            iteration=1,
            max_iterations=3,
            runner_override=override,
        )
        assert step.verdict == VerifyVerdict.ERROR
        assert step.exit_code is None
        assert "pytest-xyzzy" in step.stderr_tail

    def test_timeout_marked_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        (tmp_path / "test_slow.py").write_text("def test_slow(): pass\n")
        override = RunnerConfig(
            runner=VerifyRunner.PYTEST,
            command_prefix=[sys.executable, "-c", "import time; time.sleep(5)"],
        )
        step = run_verification(
            workspace=tmp_path,
            edited_files=[tmp_path / "test_slow.py"],
            iteration=1,
            max_iterations=3,
            timeout_seconds=1,
            runner_override=override,
        )
        assert step.verdict == VerifyVerdict.ERROR
        assert step.exit_code is None
        assert "timeout" in step.stderr_tail.lower()

    def test_default_timeout_is_reasonable(self) -> None:
        # Sanity check: don't ship an unbounded loop.
        assert DEFAULT_TIMEOUT_SECONDS > 0
        assert DEFAULT_TIMEOUT_SECONDS <= 600

    def test_edited_files_recorded_absolutely(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        (tmp_path / "test_x.py").write_text("def test_x(): pass\n")
        (tmp_path / "src.py").write_text("x=1\n")
        step = run_verification(
            workspace=tmp_path,
            edited_files=["src.py", tmp_path / "test_x.py"],
            iteration=1,
            max_iterations=1,
            runner_override=_echo_runner(exit_code=0),
        )
        assert all(p.startswith(str(tmp_path)) for p in step.files_edited_since_last_verify)

    def test_pass_populates_duration_ms(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        (tmp_path / "test_ok.py").write_text("def test_ok(): pass\n")
        step = run_verification(
            workspace=tmp_path,
            edited_files=[tmp_path / "test_ok.py"],
            iteration=1,
            max_iterations=1,
            runner_override=_echo_runner(exit_code=0),
        )
        assert step.duration_ms >= 0
        assert step.duration_ms < 5_000  # subprocess overhead is small
