"""VerificationStep schema — the structured record of a single verify iteration.

This mirrors the frontend `src/lib/schemas/verify.ts` Zod schema. Both
definitions must be kept in sync; the shared field list is enforced by
``tests/verify/test_schema_parity.py``.

The event flows through the agent-server as a paired
``ActionEvent(tool_name="verify_step") → ObservationEvent`` where the
observation's ``content`` is a JSON blob conforming to
``VerificationStep``. On the read path, ``bff/services/trace_reconstruction.py``
maps ``tool_name="verify_step"`` to span kind ``"verify"`` and the
frontend TraceTab renders it with a dedicated card.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VerifyVerdict(str, Enum):
    """Outcome of a single verify iteration."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"  # runner crashed / could not execute
    SKIPPED = "skipped"  # no test target found / policy skipped


class VerifyRunner(str, Enum):
    """Test runner detected for this iteration."""

    PYTEST = "pytest"
    VITEST = "vitest"
    JEST = "jest"
    NPM_TEST = "npm_test"
    UNKNOWN = "unknown"


class VerificationStep(BaseModel):
    """One iteration of the verify → repair loop.

    Attributes
    ----------
    iteration : int
        1-indexed position within the current verify sequence. Resets to 1
        at the start of a new task/finish attempt.
    max_iterations : int
        Retry budget for this sequence. Emitted on every event so the
        frontend can render a fractional progress indicator without
        joining across events.
    runner : VerifyRunner
        Which test runner was used.
    test_selected : list[str]
        The narrowed test targets that were actually executed (file paths,
        pytest node ids, or vitest patterns). Empty list if the runner
        could not select anything.
    command : str
        The exact shell command executed. Purely informational; the
        primary signal is ``verdict`` + ``exit_code``.
    exit_code : int | None
        Process exit code, or None if the process never started.
    stdout_tail : str
        Last ~2 KB of stdout, truncated with a leading ``…`` marker if
        truncated.
    stderr_tail : str
        Last ~2 KB of stderr, truncated the same way.
    duration_ms : int
        Wall-clock duration of the runner invocation.
    verdict : VerifyVerdict
        Structured outcome.
    files_edited_since_last_verify : list[str]
        Absolute paths of files edited between the previous verify (or
        task start) and this one. Used to correlate the verdict to a
        specific set of changes for future case retrieval
        (Recommendation 3).
    """

    model_config = ConfigDict(use_enum_values=True)

    iteration: int = Field(ge=1)
    max_iterations: int = Field(ge=1)
    runner: VerifyRunner
    test_selected: list[str] = Field(default_factory=list)
    command: str = ""
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_ms: int = Field(ge=0)
    verdict: VerifyVerdict
    files_edited_since_last_verify: list[str] = Field(default_factory=list)


# Convenience alias for the tool_name that anchors verify events.
VERIFY_STEP_TOOL_NAME: Literal["verify_step"] = "verify_step"

# Maximum size of stdout/stderr tails kept in the event (bytes).
TAIL_BYTES: int = 2048


def truncate_tail(text: str, limit: int = TAIL_BYTES) -> str:
    """Return the last ``limit`` bytes of ``text``, prefixed with ``…\\n`` when truncated."""
    if not text:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    # Trim from the head, keep the tail so tracebacks stay visible.
    truncated = encoded[-limit:].decode("utf-8", errors="replace")
    return f"…\n{truncated}"
