"""Unit tests for ``openhands_tools_ext.tool_invocation.router``.

The router is a pure function; these tests exercise:
  * every member of TOOL_HEAVY_PHASES fires True regardless of count
  * counts strictly above the threshold fire True regardless of phase
  * unknown phase + at-or-below-threshold count returns False
  * defensive: negative counts, non-string phases
"""

from __future__ import annotations

import pytest

from openhands_tools_ext.tool_invocation.router import (
    SYSTEM_PROMPT_HINT,
    TOOL_CALL_COUNT_THRESHOLD,
    TOOL_HEAVY_PHASES,
    should_use_code_execution,
)


@pytest.mark.parametrize("phase", sorted(TOOL_HEAVY_PHASES))
def test_tool_heavy_phase_fires_regardless_of_count(phase: str) -> None:
    for count in (0, 1, 3):
        assert should_use_code_execution(phase, count) is True, (
            f"expected {phase} to fire at count={count}"
        )


def test_count_above_threshold_fires_regardless_of_phase() -> None:
    assert should_use_code_execution("planning", TOOL_CALL_COUNT_THRESHOLD + 1) is True
    assert should_use_code_execution("exploration", 100) is True
    assert should_use_code_execution("", 5) is True


def test_unknown_phase_at_or_below_threshold_returns_false() -> None:
    assert should_use_code_execution("planning", 0) is False
    assert should_use_code_execution("planning", TOOL_CALL_COUNT_THRESHOLD) is False
    assert should_use_code_execution("exploration", 3) is False


def test_negative_count_clamped_to_zero() -> None:
    assert should_use_code_execution("planning", -1) is False
    assert should_use_code_execution("planning", -1000) is False
    # negative count with heavy phase still fires — phase alone is sufficient
    assert should_use_code_execution("refactor", -1) is True


def test_non_string_phase_treated_as_empty() -> None:
    # Defensive: model can send garbage; we don't crash.
    assert should_use_code_execution(None, 0) is False  # type: ignore[arg-type]
    assert should_use_code_execution(123, 0) is False  # type: ignore[arg-type]
    assert should_use_code_execution(None, 10) is True  # type: ignore[arg-type]


def test_system_prompt_hint_mentions_the_three_tool_names() -> None:
    # Sanity: the prompt hint must reference the three tools it advertises,
    # otherwise the routing story breaks silently.
    for name in ("code_execute", "list_tool_stubs", "get_tool_schema"):
        assert name in SYSTEM_PROMPT_HINT, f"missing {name!r} in system-prompt hint"
