"""Routing heuristic for code-execution invocation mode.

Pure function.  Returns True when the agent should prefer authoring a
single ``code_execute`` call over emitting many per-tool JSON invocations.

Not enforced dispatch — the model decides.  The system prompt references
this helper's logic so the model has a consistent rubric.

Design:
  * ``TOOL_HEAVY_PHASES`` is the closed set of task phases where the token
    savings from staying-in-one-code-cell dominate the overhead of the
    ``python3 -c`` invocation itself.  Kept intentionally small; adding a
    phase here is a public-API change.
  * The ``estimated_tool_call_count`` threshold (>3) is the empirical
    break-even point from the spec's cost model: three or fewer per-tool
    JSON calls are cheaper than one ``code_execute`` + its wrapped
    execution overhead.

See ``.openhands/decisions/013-code-execution-invocation-mode.md`` for the
full rationale.
"""

from __future__ import annotations

from typing import Final


TOOL_HEAVY_PHASES: Final[frozenset[str]] = frozenset(
    {"multi_file_edit", "verification", "refactor"}
)
"""Phases where code-execution mode is preferred by default.

Membership check is case-sensitive; callers should pass a normalized
snake_case phase name.
"""

TOOL_CALL_COUNT_THRESHOLD: Final[int] = 3
"""Above this many estimated per-tool calls, prefer code-execution mode.

Strict inequality: ``estimated_tool_call_count > 3`` triggers.
"""


def should_use_code_execution(
    task_phase: str,
    estimated_tool_call_count: int,
) -> bool:
    """Return True iff the agent should prefer ``code_execute`` for this step.

    Two independent triggers, either sufficient:

    1. ``task_phase`` is in :data:`TOOL_HEAVY_PHASES`.
    2. ``estimated_tool_call_count`` strictly exceeds
       :data:`TOOL_CALL_COUNT_THRESHOLD`.

    Args:
      task_phase: Normalized snake_case phase name (e.g. ``multi_file_edit``,
        ``verification``, ``refactor``, ``planning``, ``exploration``).
        Unknown phases are treated as "not tool-heavy" and fall through to
        the count check.
      estimated_tool_call_count: The agent's estimate of how many tool calls
        the current step will require.  Values ``< 0`` are treated as ``0``
        (defensive: an untrusted upstream estimator).

    Returns:
      True if either trigger fires; False otherwise.

    Examples:
      >>> should_use_code_execution("multi_file_edit", 0)
      True
      >>> should_use_code_execution("planning", 5)
      True
      >>> should_use_code_execution("planning", 3)
      False
      >>> should_use_code_execution("planning", -1)
      False
    """
    if not isinstance(task_phase, str):
        # Defensive: the model can pass anything; a non-string phase is not
        # a member of TOOL_HEAVY_PHASES by definition.
        task_phase = ""
    count = max(0, int(estimated_tool_call_count))
    return task_phase in TOOL_HEAVY_PHASES or count > TOOL_CALL_COUNT_THRESHOLD


SYSTEM_PROMPT_HINT: Final[str] = (
    "When your next step involves editing multiple files, running a "
    "verification pass, or refactoring — or when you estimate more than "
    "three tool calls — prefer calling the `code_execute` tool with a "
    "single Python program that itself calls the other tools by name, "
    "rather than emitting per-tool JSON. This keeps intermediate results "
    "and unused tool schemas out of your context window. Use "
    "`list_tool_stubs` to discover tool names and `get_tool_schema` to "
    "load the full schema for a specific tool only when you need it."
)
"""Verbatim hint threaded into the agent's system prompt.

The hint mirrors :func:`should_use_code_execution`'s logic so the model has
one rubric it applies consistently.  The prompt-assembly path that threads
this hint is out of scope for §6.7 — see ADR 013.
"""
