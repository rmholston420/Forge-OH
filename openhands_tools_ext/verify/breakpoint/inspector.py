"""Runtime state inspection at instrumented breakpoints.

Adapts the pattern from ``FloridSleeves/LLMDebugger`` (LDB, Apache-2.0)
into a form usable by the OpenHands sandbox: run a Python script (or a
callable) with ``sys.settrace``, capture the local-variable state at
each executed line inside a caller-supplied set of ``(filename, lineno)``
breakpoints, and return the trace as a structured record.

The LDB paper's contribution is showing that an LLM debugging by
inspecting *runtime state per block* beats reasoning over static code
alone. Their implementation is CLI/benchmark-harness-shaped (see
``programming/tracing/tracer.py`` upstream: hard-coded ``.tmp.py`` file
path, vendored ``staticfg`` CFG builder, ``astroid`` dependency). This
port keeps only the pattern:

  * ``sys.settrace`` line hook rather than ``pdb.Pdb`` — pdb is
    interactive-loop shaped and blocks on stdin.
  * User-supplied breakpoint list rather than automatic CFG-block
    breakpoints. The agent decides where to inspect; we just record.
  * Snapshot of ``frame.f_locals`` at each hit, rendered as ``repr`` so
    the transcript is text-safe and bounded.

See PORTING_LEDGER.md entry for the exact upstream commit hash and the
list of design points adapted vs. discarded.
"""

from __future__ import annotations

import io
import runpy
import sys
import types
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Cap the repr length of any single local variable snapshot. LDB's
# tracer has similar guard rails but hard-coded further inside their
# prompt template; we make it an explicit constant.
MAX_REPR_LEN: int = 200
MAX_HITS: int = 200


@dataclass(frozen=True)
class Breakpoint:
    """A single (filename, lineno) breakpoint the tracer will react to."""

    filename: str
    lineno: int


@dataclass
class BreakpointHit:
    """One recorded snapshot at a breakpoint."""

    breakpoint: Breakpoint
    order: int
    local_reprs: dict[str, str] = field(default_factory=dict)


@dataclass
class InspectionResult:
    """The full outcome of an inspection run."""

    hits: list[BreakpointHit]
    stdout: str
    stderr: str
    exception: str | None
    truncated: bool  # True if MAX_HITS was reached and later hits were dropped


def _safe_repr(value: Any, limit: int = MAX_REPR_LEN) -> str:
    """Best-effort repr that never raises and never returns a giant string."""
    try:
        rendered = repr(value)
    except Exception as exc:
        return f"<unrepr-able: {type(value).__name__}: {exc!r}>"
    if len(rendered) <= limit:
        return rendered
    return rendered[: limit - 3] + "..."


def inspect_script(
    script_path: Path,
    breakpoints: list[Breakpoint],
    *,
    argv: list[str] | None = None,
) -> InspectionResult:
    """Run ``script_path`` under a line tracer that records state at each breakpoint.

    Parameters
    ----------
    script_path
        Absolute path to a Python source file. Executed via
        :func:`runpy.run_path` so ``__main__`` semantics match the user's
        normal invocation.
    breakpoints
        (filename, lineno) pairs at which to snapshot ``frame.f_locals``.
        Filenames are matched by *basename* (LDB's approach), because a
        script running under runpy has ``__file__`` set to the original
        path and Python's trace frames carry the same. We compare
        basenames only to tolerate absolute/relative discrepancies.
    argv
        Additional command-line arguments for the script (assigned to
        ``sys.argv[1:]``). ``sys.argv[0]`` is always the script path.

    Returns
    -------
    InspectionResult
        Ordered list of hits, captured stdout/stderr, exception text if
        the script raised, and a ``truncated`` flag if we clipped at
        ``MAX_HITS``.
    """
    hits: list[BreakpointHit] = []
    truncated = False
    bp_index: dict[tuple[str, int], Breakpoint] = {
        (Path(bp.filename).name, bp.lineno): bp for bp in breakpoints
    }

    order = 0

    def tracer(
        frame: types.FrameType,
        event: str,
        _arg: Any,
    ) -> Any:
        nonlocal order, truncated
        if event != "line":
            return tracer
        code = frame.f_code
        key = (Path(code.co_filename).name, frame.f_lineno)
        bp = bp_index.get(key)
        if bp is None:
            return tracer
        if len(hits) >= MAX_HITS:
            truncated = True
            return tracer
        snapshot = {name: _safe_repr(value) for name, value in frame.f_locals.items()}
        hits.append(BreakpointHit(breakpoint=bp, order=order, local_reprs=snapshot))
        order += 1
        return tracer

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exception_text: str | None = None

    saved_argv = sys.argv[:]
    sys.argv = [str(script_path)] + (argv or [])
    sys.settrace(tracer)
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                runpy.run_path(str(script_path), run_name="__main__")
            except SystemExit:
                # Scripts commonly call sys.exit(); not an error for us.
                pass
            except BaseException as exc:
                exception_text = f"{type(exc).__name__}: {exc}"
    finally:
        sys.settrace(None)
        sys.argv = saved_argv

    return InspectionResult(
        hits=hits,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
        exception=exception_text,
        truncated=truncated,
    )


def summarize_for_llm(result: InspectionResult, *, max_hits: int = 20) -> str:
    """Render an ``InspectionResult`` as text suitable for LLM context.

    Follows LDB's pattern of one block per hit with an inline
    ``k=v; k=v; …`` local-variable line, but capped at ``max_hits`` so
    the resulting string is bounded regardless of loop iterations.
    """
    if not result.hits:
        if result.exception:
            return f"[no hits] script raised: {result.exception}"
        return "[no hits]"

    lines: list[str] = []
    shown = result.hits[:max_hits]
    for hit in shown:
        locals_line = "; ".join(f"{name}={value}" for name, value in hit.local_reprs.items())
        lines.append(
            f"[{hit.order}] {hit.breakpoint.filename}:{hit.breakpoint.lineno}  {locals_line}"
        )
    if len(result.hits) > max_hits:
        lines.append(
            f"… {len(result.hits) - max_hits} more hits omitted (result.truncated={result.truncated})"
        )
    if result.exception:
        lines.append(f"[exception] {result.exception}")
    return "\n".join(lines)
