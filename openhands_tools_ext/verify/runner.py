"""Runner invocation: execute a selected test command and produce a VerificationStep.

This is the deterministic, testable core of Slice E. Given a workspace,
a set of edited files, and a retry-loop position (iteration /
max_iterations), it:

  1. Detects the runner (:func:`selector.detect_runner`).
  2. Selects targets (:func:`selector.select_targets`).
  3. Executes the subprocess with a bounded timeout.
  4. Packages stdout/stderr tails, exit code, wall-clock duration, and
     verdict into a :class:`VerificationStep`.

The verdict mapping is intentionally coarse:

  - exit_code == 0                 -> pass
  - exit_code != 0                 -> fail
  - subprocess.TimeoutExpired      -> error
  - runner not detected or targets empty -> skipped (no subprocess call)

Callers (the hook plugin in E.4) are responsible for retry policy and
event emission. This module never emits events -- it only computes.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

from openhands_tools_ext.verify.schema import (
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
    truncate_tail,
)
from openhands_tools_ext.verify.selector import (
    RunnerConfig,
    build_command,
    detect_runner,
    select_targets,
)

DEFAULT_TIMEOUT_SECONDS: int = 120


def run_verification(
    workspace: Path,
    edited_files: Iterable[str | Path],
    *,
    iteration: int,
    max_iterations: int,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    runner_override: RunnerConfig | None = None,
) -> VerificationStep:
    """Execute one verify iteration end to end.

    Parameters
    ----------
    workspace
        Absolute path to the workspace root. Used to detect the runner
        and as the cwd of the subprocess.
    edited_files
        Absolute or workspace-relative file paths edited since the last
        verify. Used to narrow test targets.
    iteration, max_iterations
        Position in the retry loop, echoed onto the resulting event.
    timeout_seconds
        Wall-clock ceiling for the subprocess. On timeout the verdict is
        ``error`` and ``exit_code`` is ``None``.
    runner_override
        Skip auto-detection and use the supplied config. Handy for tests
        and for callers that already know the runner.
    """
    edited_snapshot = [
        str(Path(p).resolve()) if Path(p).is_absolute() else str(workspace / p)
        for p in edited_files
    ]

    config = runner_override or detect_runner(workspace)
    if config is None:
        return VerificationStep(
            iteration=iteration,
            max_iterations=max_iterations,
            runner=VerifyRunner.UNKNOWN,
            test_selected=[],
            command="",
            exit_code=None,
            stdout_tail="",
            stderr_tail="no runner detected in workspace",
            duration_ms=0,
            verdict=VerifyVerdict.SKIPPED,
            files_edited_since_last_verify=edited_snapshot,
        )

    targets = select_targets(workspace, edited_files, config.runner)
    if not targets:
        return VerificationStep(
            iteration=iteration,
            max_iterations=max_iterations,
            runner=config.runner,
            test_selected=[],
            command=" ".join(config.command_prefix),
            exit_code=None,
            stdout_tail="",
            stderr_tail="no test targets selected for the edited files",
            duration_ms=0,
            verdict=VerifyVerdict.SKIPPED,
            files_edited_since_last_verify=edited_snapshot,
        )

    argv = build_command(config, targets)
    return _execute(
        argv=argv,
        cwd=workspace,
        runner=config.runner,
        targets=targets,
        iteration=iteration,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        edited_snapshot=edited_snapshot,
    )


def _execute(
    *,
    argv: Sequence[str],
    cwd: Path,
    runner: VerifyRunner,
    targets: list[str],
    iteration: int,
    max_iterations: int,
    timeout_seconds: int,
    edited_snapshot: list[str],
) -> VerificationStep:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return VerificationStep(
            iteration=iteration,
            max_iterations=max_iterations,
            runner=runner,
            test_selected=targets,
            command=" ".join(argv),
            exit_code=None,
            stdout_tail=truncate_tail(
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            ),
            stderr_tail=truncate_tail(
                (
                    exc.stderr.decode(errors="replace")
                    if isinstance(exc.stderr, bytes)
                    else (exc.stderr or "")
                )
                + f"\n[verify] runner exceeded timeout of {timeout_seconds}s"
            ),
            duration_ms=duration_ms,
            verdict=VerifyVerdict.ERROR,
            files_edited_since_last_verify=edited_snapshot,
        )
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return VerificationStep(
            iteration=iteration,
            max_iterations=max_iterations,
            runner=runner,
            test_selected=targets,
            command=" ".join(argv),
            exit_code=None,
            stdout_tail="",
            stderr_tail=f"[verify] {exc.strerror or 'runner not found'}: {argv[0]}",
            duration_ms=duration_ms,
            verdict=VerifyVerdict.ERROR,
            files_edited_since_last_verify=edited_snapshot,
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    verdict = VerifyVerdict.PASS if proc.returncode == 0 else VerifyVerdict.FAIL
    return VerificationStep(
        iteration=iteration,
        max_iterations=max_iterations,
        runner=runner,
        test_selected=targets,
        command=" ".join(argv),
        exit_code=proc.returncode,
        stdout_tail=truncate_tail(proc.stdout or ""),
        stderr_tail=truncate_tail(proc.stderr or ""),
        duration_ms=duration_ms,
        verdict=verdict,
        files_edited_since_last_verify=edited_snapshot,
    )
