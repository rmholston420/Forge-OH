"""Unit tests for ``code_execute`` — the code-execution invocation mode tool.

These tests exercise the real subprocess path: a working ``python3`` on
$PATH is required (assumed on Colossus and every dev machine).  We keep
the programs tiny so the whole file runs in <2s.
"""

from __future__ import annotations

import shutil

import pytest

from openhands.sdk.tool.registry import list_registered_tools
from openhands_tools_ext.tool_invocation import code_exec_mode as cem


pytestmark = pytest.mark.skipif(
    shutil.which("python3") is None,
    reason="code_execute requires python3 on PATH",
)


def test_module_registers_code_execute() -> None:
    assert "code_execute" in list_registered_tools()


def test_happy_path_prints_stdout_and_returns_zero_exit() -> None:
    executor = cem.CodeExecuteExecutor()
    obs = executor(cem.CodeExecuteAction(python_code="print(2 + 2)"))

    assert obs.exit_code == 0
    assert obs.timed_out is False
    assert obs.stdout.strip() == "4"
    assert obs.stderr == ""
    assert obs.stdout_truncated is False
    assert obs.stderr_truncated is False
    assert obs.duration_sec >= 0.0


def test_nonzero_exit_captured() -> None:
    executor = cem.CodeExecuteExecutor()
    obs = executor(cem.CodeExecuteAction(python_code="import sys; sys.exit(7)"))
    assert obs.exit_code == 7
    assert obs.timed_out is False


def test_stderr_captured() -> None:
    executor = cem.CodeExecuteExecutor()
    obs = executor(
        cem.CodeExecuteAction(
            python_code="import sys; sys.stderr.write('oops'); sys.exit(0)"
        )
    )
    assert obs.exit_code == 0
    assert "oops" in obs.stderr


def test_timeout_kills_runaway_program(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the 1s minimum-clamped timeout so this test is fast.
    monkeypatch.setenv(cem.TIMEOUT_ENV, "1")
    executor = cem.CodeExecuteExecutor()
    obs = executor(
        cem.CodeExecuteAction(python_code="import time; time.sleep(30)")
    )
    assert obs.timed_out is True
    assert obs.exit_code != 0
    assert "TIMEOUT" in obs.stderr


def test_stdout_truncated_when_exceeds_max_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(cem.MAX_OUTPUT_ENV, "1000")  # clamped to floor of 1000
    executor = cem.CodeExecuteExecutor()
    obs = executor(
        cem.CodeExecuteAction(python_code="print('x' * 5000)")
    )
    assert obs.exit_code == 0
    assert obs.stdout_truncated is True
    # Truncated output must be at most the limit (with 1-byte margin for
    # UTF-8-safe re-decode dropping a boundary byte).
    assert len(obs.stdout.encode("utf-8")) <= 1000


def test_shell_metacharacters_are_inert() -> None:
    # The tool uses argv (no shell), so a semicolon in python_code is Python
    # syntax — not a shell separator.  Verify it's evaluated by python3.
    executor = cem.CodeExecuteExecutor()
    obs = executor(
        cem.CodeExecuteAction(python_code="a=1;b=2;print(a+b)")
    )
    assert obs.exit_code == 0
    assert obs.stdout.strip() == "3"


def test_truncate_helper_utf8_safe() -> None:
    text = "é" * 1000  # each 'é' is 2 bytes in UTF-8
    truncated, was = cem._truncate(text, 50)
    assert was is True
    # Must be decodable — no split multi-byte sequence at the boundary.
    _ = truncated.encode("utf-8")


def test_config_env_clamps() -> None:
    # Timeout floor/ceiling
    import os

    os.environ[cem.TIMEOUT_ENV] = "0"
    assert cem._timeout_sec() == 1  # clamped up
    os.environ[cem.TIMEOUT_ENV] = "9999"
    assert cem._timeout_sec() == 300  # clamped down
    os.environ[cem.TIMEOUT_ENV] = "not-an-int"
    assert cem._timeout_sec() == cem.TIMEOUT_DEFAULT_SEC
    del os.environ[cem.TIMEOUT_ENV]

    # Max-output floor/ceiling
    os.environ[cem.MAX_OUTPUT_ENV] = "100"
    assert cem._max_output_bytes() == 1000  # clamped up
    os.environ[cem.MAX_OUTPUT_ENV] = "9999999"
    assert cem._max_output_bytes() == 1_000_000  # clamped down
    del os.environ[cem.MAX_OUTPUT_ENV]
