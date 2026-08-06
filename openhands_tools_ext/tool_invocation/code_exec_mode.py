"""``code_execute`` — Stage 6.7 code-execution-with-MCP invocation mode.

The agent authors a Python program that itself calls other registered
tools by name (in-code, not via per-tool JSON), keeping intermediate
results and unused schemas out of the model's context window.

Sandbox tier (see ADR 013):
  The agent-server process IS the sandbox tier for Colossus's
  single-user local-first topology (ADR 002 keeps agent-server behind
  the BFF; there is no public port).  ``code_execute`` runs the
  agent-authored program via ``python3 -c`` in a subprocess of the
  agent-server, inheriting the same execution boundary every ``bash``
  action already crosses.  This is **not** a bare ``exec()`` inside the
  BFF: the BFF never sees the program text.  The subprocess is
  wall-clock-bounded and output-truncated so a runaway program cannot
  hang or flood the ledger.

Registration is at import time; add
``--import-modules openhands_tools_ext.tool_invocation.code_exec_mode``
to the agent-server launch line.
"""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404 — bounded, agent-authored, single-user local
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field

from openhands.sdk.tool.registry import register_tool
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.sdk.conversation.state import ConversationState


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config (env-overridable so Colossus can tune without a code change)
# ---------------------------------------------------------------------------

TIMEOUT_ENV = "FORGE_CODE_EXECUTE_TIMEOUT_SEC"
TIMEOUT_DEFAULT_SEC = 30

MAX_OUTPUT_ENV = "FORGE_CODE_EXECUTE_MAX_OUTPUT_BYTES"
MAX_OUTPUT_DEFAULT = 64_000

CWD_ENV = "FORGE_CODE_EXECUTE_CWD"  # optional; else agent-server cwd


def _timeout_sec() -> int:
    raw = os.environ.get(TIMEOUT_ENV)
    if not raw:
        return TIMEOUT_DEFAULT_SEC
    try:
        parsed = int(raw)
    except ValueError:
        return TIMEOUT_DEFAULT_SEC
    return max(1, min(parsed, 300))  # clamp 1..300s


def _max_output_bytes() -> int:
    raw = os.environ.get(MAX_OUTPUT_ENV)
    if not raw:
        return MAX_OUTPUT_DEFAULT
    try:
        parsed = int(raw)
    except ValueError:
        return MAX_OUTPUT_DEFAULT
    return max(1_000, min(parsed, 1_000_000))  # clamp 1KB..1MB


def _truncate(text: str, limit_bytes: int) -> tuple[str, bool]:
    """Return (text, was_truncated).  UTF-8-safe truncation by encoded length."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit_bytes:
        return text, False
    # Trim by encoded byte length, then re-decode with 'ignore' to drop any
    # split multi-byte sequence at the boundary.
    return encoded[:limit_bytes].decode("utf-8", errors="ignore"), True


# ---------------------------------------------------------------------------
# Action / Observation
# ---------------------------------------------------------------------------


class CodeExecuteAction(Action):
    """Run ``python_code`` in the agent-server subprocess sandbox tier.

    ``python_code`` is executed by ``python3 -c '<code>'`` and inherits
    the agent-server's cwd and env.  Intended for programs that call
    other registered tools programmatically — but any Python is
    accepted; the sandbox tier is the same as ``bash``.
    """

    python_code: str = Field(
        min_length=1,
        max_length=100_000,
        description=(
            "Python source to execute.  Program should print any results "
            "the agent needs to observe.  Import other tools from "
            "``openhands.sdk.tool.registry`` and invoke them by name."
        ),
    )


class CodeExecuteObservation(Observation):
    exit_code: int
    stdout: str
    stderr: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False
    duration_sec: float = 0.0

    @property
    def agent_observation(self) -> Sequence[Any]:  # pragma: no cover
        return ()


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class CodeExecuteExecutor(ToolExecutor[CodeExecuteAction, CodeExecuteObservation]):
    """Run agent-authored Python in a bounded subprocess of the agent-server.

    Bounds:
      * wall-clock timeout (``FORGE_CODE_EXECUTE_TIMEOUT_SEC``, default 30s)
      * stdout/stderr truncation (``FORGE_CODE_EXECUTE_MAX_OUTPUT_BYTES``,
        default 64_000)

    Uses ``subprocess.run`` with a fixed ``argv`` list — no shell, no
    string interpolation, so shell metacharacters in ``python_code`` are
    inert.  ``python_code`` reaches the child interpreter through argv,
    not the shell.
    """

    def __call__(
        self,
        action: CodeExecuteAction,
        conversation: "BaseConversation | None" = None,  # noqa: ARG002
    ) -> CodeExecuteObservation:
        timeout = _timeout_sec()
        max_bytes = _max_output_bytes()
        cwd = os.environ.get(CWD_ENV) or None

        argv = ["python3", "-c", action.python_code]

        import time

        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(  # nosec B603 — argv list; no shell
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                cwd=cwd,
            )
            exit_code = completed.returncode
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            stderr = (stderr + f"\n[code_execute] TIMEOUT after {timeout}s").lstrip()
        duration = round(time.monotonic() - started, 4)

        stdout_trunc, stdout_was_trunc = _truncate(stdout, max_bytes)
        stderr_trunc, stderr_was_trunc = _truncate(stderr, max_bytes)

        return CodeExecuteObservation(
            exit_code=exit_code,
            stdout=stdout_trunc,
            stderr=stderr_trunc,
            stdout_truncated=stdout_was_trunc,
            stderr_truncated=stderr_was_trunc,
            timed_out=timed_out,
            duration_sec=duration,
        )


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


CODE_EXECUTE_DESCRIPTION = """Run agent-authored Python via ``python3 -c`` inside the agent-server sandbox tier.

Use this when your next step involves multiple tool calls, editing many
files, running a verification pass, or refactoring.  Author a single
Python program that itself calls the tools you need — the intermediate
results and unused tool schemas stay out of your context window.

Parameters:
- python_code: The Python program to execute.  Print anything you want
  to observe; the tool returns stdout/stderr/exit_code.

Bounds:
- Wall-clock timeout: 30s (configurable via ``FORGE_CODE_EXECUTE_TIMEOUT_SEC``).
- stdout/stderr each truncated to 64,000 bytes (configurable via
  ``FORGE_CODE_EXECUTE_MAX_OUTPUT_BYTES``).

Returns {exit_code, stdout, stderr, stdout_truncated, stderr_truncated,
timed_out, duration_sec}.  ``exit_code=0`` means the program returned
normally; a non-zero code or ``timed_out=true`` means the program failed
or was killed at the timeout.
"""


class CodeExecuteTool(ToolDefinition[CodeExecuteAction, CodeExecuteObservation]):
    """SDK tool wrapper for :class:`CodeExecuteExecutor`."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,  # noqa: ARG003
        **params: Any,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(
                "CodeExecuteTool does not accept factory parameters "
                f"(got {sorted(params)})"
            )
        return [
            cls(
                action_type=CodeExecuteAction,
                observation_type=CodeExecuteObservation,
                description=CODE_EXECUTE_DESCRIPTION,
                executor=CodeExecuteExecutor(),
                annotations=ToolAnnotations(
                    title="code_execute",
                    readOnlyHint=False,
                    destructiveHint=True,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
            )
        ]


register_tool("code_execute", CodeExecuteTool)
