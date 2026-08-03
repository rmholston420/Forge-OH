"""Tests for the runtime breakpoint inspector."""

from __future__ import annotations

from pathlib import Path

from openhands_tools_ext.verify.breakpoint.inspector import (
    MAX_HITS,
    Breakpoint,
    inspect_script,
    summarize_for_llm,
)


def _write_script(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(source)
    return p


class TestInspectScript:
    def test_hits_recorded_at_matching_line(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "s.py",
            "x = 1\ny = x + 2\nprint(y)\n",
        )
        result = inspect_script(script, [Breakpoint("s.py", 2)])
        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.breakpoint.lineno == 2
        assert hit.local_reprs["x"] == "1"
        assert result.stdout.strip() == "3"
        assert result.exception is None

    def test_multiple_breakpoints_ordered_by_execution(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "s.py",
            "a = 10\nb = 20\nc = a + b\n",
        )
        result = inspect_script(
            script,
            [
                Breakpoint("s.py", 3),  # c = a + b — has a and b in locals
                Breakpoint("s.py", 2),  # b = 20 — only a in locals
            ],
        )
        assert [h.breakpoint.lineno for h in result.hits] == [2, 3]
        # At line 2 only 'a' is defined; at line 3 both a and b are.
        assert "a" in result.hits[0].local_reprs
        assert "b" not in result.hits[0].local_reprs
        assert result.hits[1].local_reprs.get("a") == "10"
        assert result.hits[1].local_reprs.get("b") == "20"

    def test_no_breakpoints_yields_no_hits(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "s.py", "print('hi')\n")
        result = inspect_script(script, [])
        assert result.hits == []
        assert "hi" in result.stdout

    def test_breakpoint_on_unused_line_never_fires(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "s.py",
            "x = 1\nif False:\n    x = 2\nprint(x)\n",
        )
        result = inspect_script(script, [Breakpoint("s.py", 3)])
        assert result.hits == []

    def test_exception_captured_and_traced_lines_still_hit(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "s.py",
            "x = 1\ny = 0\nz = x / y\n",
        )
        result = inspect_script(
            script,
            [Breakpoint("s.py", 3)],
        )
        # The tracer sees the 'line' event before the exception fires.
        assert len(result.hits) == 1
        assert result.exception is not None
        assert "ZeroDivisionError" in result.exception

    def test_hit_limit_marks_truncated(self, tmp_path: Path) -> None:
        # Loop far more times than MAX_HITS; expect the tracer to clip.
        n = MAX_HITS + 10
        script = _write_script(
            tmp_path,
            "s.py",
            f"total = 0\nfor i in range({n}):\n    total += 1\n",
        )
        result = inspect_script(script, [Breakpoint("s.py", 3)])
        assert result.truncated is True
        assert len(result.hits) == MAX_HITS

    def test_local_repr_bounded(self, tmp_path: Path) -> None:
        # A huge object should not blow up the repr size.
        script = _write_script(
            tmp_path,
            "s.py",
            "big = 'x' * 100_000\nsentinel = 1\n",
        )
        result = inspect_script(script, [Breakpoint("s.py", 2)])
        assert len(result.hits) == 1
        # big is one of the locals; its repr must be truncated.
        assert len(result.hits[0].local_reprs["big"]) <= 220

    def test_unrepr_able_local_does_not_crash(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "s.py",
            (
                "class Boom:\n"
                "    def __repr__(self):\n"
                "        raise RuntimeError('nope')\n"
                "b = Boom()\n"
                "sentinel = 1\n"
            ),
        )
        result = inspect_script(script, [Breakpoint("s.py", 5)])
        assert len(result.hits) == 1
        assert "unrepr-able" in result.hits[0].local_reprs["b"]


class TestSummarizeForLlm:
    def test_empty_result_renders_no_hits(self) -> None:
        from openhands_tools_ext.verify.breakpoint.inspector import (
            InspectionResult,
        )

        s = summarize_for_llm(
            InspectionResult(hits=[], stdout="", stderr="", exception=None, truncated=False)
        )
        assert s == "[no hits]"

    def test_hits_rendered_with_locals(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "s.py", "a = 1\nb = 2\n")
        result = inspect_script(script, [Breakpoint("s.py", 2)])
        text = summarize_for_llm(result)
        assert "s.py:2" in text
        assert "a=1" in text

    def test_cap_shows_ellipsis_line(self, tmp_path: Path) -> None:
        script = _write_script(tmp_path, "s.py", "total = 0\nfor i in range(50):\n    total += 1\n")
        result = inspect_script(script, [Breakpoint("s.py", 3)])
        text = summarize_for_llm(result, max_hits=5)
        assert "more hits omitted" in text
