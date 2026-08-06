#!/usr/bin/env python3
"""Token-usage comparison for Path A (direct vLLM) vs Path B (Forge-OH stack).

Reads two run directories under ~/.forge-oh/bench_*/ and emits per-task and
aggregate deltas. Purpose: attribute the token/wall/tool-call cost of the
Forge-OH middleware stack (Stage 3-6 features) versus the raw vLLM baseline.

Path A record shape (bench_pathF_swebench.py):
  prompt_tokens, completion_tokens, tok_per_s, wall_seconds, resolved

Path B record shape (bench_pathB.py):
  metrics.token_count (total across all LLM calls in the trajectory)
  metrics.tool_call_count
  wall_seconds (agent-trajectory wall, not just LLM inference)
  resolved

The comparison intentionally treats:
  - Path A wall = single LLM completion time
  - Path B wall = full agent trajectory time (all tool calls + all LLM calls)
  - Path A tokens = single completion prompt+completion
  - Path B tokens = sum across every LLM call in the trajectory

That's the point of the delta: the stack costs what it costs.

Usage
-----
    python -m bench.pathF_swebench.compare_tokens \\
        --path-a ~/.forge-oh/bench_pathF_swebench/20260806_1211_run \\
        --path-b ~/.forge-oh/bench_pathB_swebench/20260806_XXXX_run \\
        --out ~/.forge-oh/bench_compare/compare_$(date +%Y%m%d_%H%M).md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------- Loaders ----------


def _load_run_dir(run_dir: Path) -> dict[str, dict]:
    """Load every per-task JSON in a run directory into {instance_id: record}."""
    tasks: dict[str, dict] = {}
    for p in sorted(run_dir.glob("*.json")):
        if p.name in ("manifest.json", "_summary.json"):
            continue
        try:
            rec = json.loads(p.read_text())
            iid = rec.get("instance_id") or p.stem
            tasks[iid] = rec
        except Exception as exc:
            print(f"[compare] warn: failed to parse {p}: {exc}", file=sys.stderr)
    return tasks


def _load_summary(run_dir: Path) -> dict:
    p = run_dir / "_summary.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


# ---------- Per-task extraction ----------


def _path_a_metrics(rec: dict) -> dict:
    """Extract comparable metrics from a Path A record."""
    return {
        "prompt_tokens": int(rec.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(rec.get("completion_tokens", 0) or 0),
        "total_tokens": int(rec.get("prompt_tokens", 0) or 0) + int(rec.get("completion_tokens", 0) or 0),
        "wall_seconds": float(rec.get("wall_seconds", 0) or 0),
        "tool_call_count": 0,   # Path A is single-shot; no tool calls.
        "resolved": bool(rec.get("resolved") is True),
        "truncated": bool(rec.get("truncated_by_length", False)),
        "error": rec.get("error"),
    }


def _path_b_metrics(rec: dict) -> dict:
    """Extract comparable metrics from a Path B record."""
    metrics = rec.get("metrics") or {}
    return {
        "prompt_tokens": None,   # aggregated in `total_tokens`
        "completion_tokens": None,
        "total_tokens": int(metrics.get("token_count", 0) or 0),
        "wall_seconds": float(rec.get("wall_seconds", 0) or 0),
        "tool_call_count": int(rec.get("tool_call_count", metrics.get("tool_call_count", 0)) or 0),
        "resolved": bool(rec.get("resolved") is True),
        "terminal_reason": rec.get("terminal_reason"),
        "terminal_status": rec.get("terminal_status"),
        "error": rec.get("error"),
    }


# ---------- Comparison ----------


def _fmt_int(n) -> str:
    if n is None:
        return "—"
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _fmt_float(n, digits: int = 2) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):.{digits}f}"
    except Exception:
        return str(n)


def _delta(a, b) -> str:
    """b - a, formatted with sign. None-safe."""
    if a is None or b is None:
        return "—"
    try:
        d = float(b) - float(a)
        sign = "+" if d > 0 else ""
        return f"{sign}{d:,.2f}"
    except Exception:
        return "—"


def _resolved_status(a: dict, b: dict) -> str:
    """Return one of: agree_pass, agree_fail, a_only, b_only."""
    ar, br = a["resolved"], b["resolved"]
    if ar and br:
        return "agree_pass"
    if not ar and not br:
        return "agree_fail"
    if ar and not br:
        return "a_only (regression)"
    if br and not ar:
        return "b_only (improvement)"
    return "unknown"


def compare(
    path_a_dir: Path, path_b_dir: Path,
) -> tuple[list[dict], dict]:
    a_tasks = _load_run_dir(path_a_dir)
    b_tasks = _load_run_dir(path_b_dir)
    a_summary = _load_summary(path_a_dir)
    b_summary = _load_summary(path_b_dir)

    all_ids = sorted(set(a_tasks.keys()) | set(b_tasks.keys()))
    rows: list[dict] = []

    for iid in all_ids:
        if iid in a_tasks and iid in b_tasks:
            am = _path_a_metrics(a_tasks[iid])
            bm = _path_b_metrics(b_tasks[iid])
            rows.append({
                "instance_id": iid,
                "in_both": True,
                "resolved_status": _resolved_status(am, bm),
                "path_a": am,
                "path_b": bm,
                "delta_tokens": (
                    bm["total_tokens"] - am["total_tokens"]
                    if am["total_tokens"] and bm["total_tokens"]
                    else None
                ),
                "delta_wall_s": bm["wall_seconds"] - am["wall_seconds"],
                "delta_tool_calls": bm["tool_call_count"] - am["tool_call_count"],
            })
        elif iid in a_tasks:
            rows.append({
                "instance_id": iid,
                "in_both": False,
                "only_in": "A",
                "path_a": _path_a_metrics(a_tasks[iid]),
            })
        else:
            rows.append({
                "instance_id": iid,
                "in_both": False,
                "only_in": "B",
                "path_b": _path_b_metrics(b_tasks[iid]),
            })

    # Aggregates over tasks present in BOTH.
    both = [r for r in rows if r.get("in_both")]
    a_totals = {
        "tokens": sum((r["path_a"]["total_tokens"] or 0) for r in both),
        "wall": sum(r["path_a"]["wall_seconds"] for r in both),
        "tool_calls": sum(r["path_a"]["tool_call_count"] for r in both),
        "resolved": sum(1 for r in both if r["path_a"]["resolved"]),
    }
    b_totals = {
        "tokens": sum((r["path_b"]["total_tokens"] or 0) for r in both),
        "wall": sum(r["path_b"]["wall_seconds"] for r in both),
        "tool_calls": sum(r["path_b"]["tool_call_count"] for r in both),
        "resolved": sum(1 for r in both if r["path_b"]["resolved"]),
    }

    agg = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "path_a_dir": str(path_a_dir),
        "path_b_dir": str(path_b_dir),
        "path_a_summary": a_summary,
        "path_b_summary": b_summary,
        "task_count_both": len(both),
        "task_count_a_only": sum(1 for r in rows if not r.get("in_both") and r.get("only_in") == "A"),
        "task_count_b_only": sum(1 for r in rows if not r.get("in_both") and r.get("only_in") == "B"),
        "path_a_totals": a_totals,
        "path_b_totals": b_totals,
        "delta_totals": {
            "tokens": b_totals["tokens"] - a_totals["tokens"],
            "wall_s": b_totals["wall"] - a_totals["wall"],
            "tool_calls": b_totals["tool_calls"] - a_totals["tool_calls"],
            "resolved": b_totals["resolved"] - a_totals["resolved"],
        },
        "regression_ids": [r["instance_id"] for r in both if r["resolved_status"] == "a_only (regression)"],
        "improvement_ids": [r["instance_id"] for r in both if r["resolved_status"] == "b_only (improvement)"],
        "token_ratio_b_over_a": (
            round(b_totals["tokens"] / a_totals["tokens"], 2)
            if a_totals["tokens"] > 0 else None
        ),
        "wall_ratio_b_over_a": (
            round(b_totals["wall"] / a_totals["wall"], 2)
            if a_totals["wall"] > 0 else None
        ),
    }

    return rows, agg


# ---------- Renderers ----------


def render_markdown(rows: list[dict], agg: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Path A vs Path B — token & cost comparison")
    lines.append("")
    lines.append(f"- Generated: `{agg['generated_at_utc']}`")
    lines.append(f"- Path A run: `{agg['path_a_dir']}`")
    lines.append(f"- Path B run: `{agg['path_b_dir']}`")
    lines.append(f"- Tasks in both: **{agg['task_count_both']}**  ")
    lines.append(f"  a-only: {agg['task_count_a_only']} · b-only: {agg['task_count_b_only']}")
    lines.append("")

    lines.append("## Aggregate")
    lines.append("")
    lines.append("| Metric | Path A | Path B | Δ (B − A) | B/A |")
    lines.append("|---|---:|---:|---:|---:|")
    aa, bb, dd = agg["path_a_totals"], agg["path_b_totals"], agg["delta_totals"]
    ratio_tok = agg["token_ratio_b_over_a"]
    ratio_wall = agg["wall_ratio_b_over_a"]
    lines.append(f"| Resolved (pass@1) | {aa['resolved']} | {bb['resolved']} | {dd['resolved']:+d} | — |")
    lines.append(f"| Total tokens | {_fmt_int(aa['tokens'])} | {_fmt_int(bb['tokens'])} | {_fmt_int(dd['tokens'])} | {ratio_tok if ratio_tok is not None else '—'}× |")
    lines.append(f"| Wall (seconds, sum) | {_fmt_float(aa['wall'])} | {_fmt_float(bb['wall'])} | {_fmt_float(dd['wall_s'])} | {ratio_wall if ratio_wall is not None else '—'}× |")
    lines.append(f"| Tool calls (sum) | {aa['tool_calls']} | {bb['tool_calls']} | {dd['tool_calls']:+d} | — |")
    lines.append("")

    if agg["regression_ids"]:
        lines.append("## Regressions (A passed, B failed)")
        for iid in agg["regression_ids"]:
            lines.append(f"- `{iid}`")
        lines.append("")

    if agg["improvement_ids"]:
        lines.append("## Improvements (B passed, A failed)")
        for iid in agg["improvement_ids"]:
            lines.append(f"- `{iid}`")
        lines.append("")

    lines.append("## Per-task breakdown")
    lines.append("")
    lines.append("| Task | Status | A tok | B tok | Δ tok | A wall | B wall | Δ wall | B tools |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        if not r.get("in_both"):
            side = r.get("only_in", "?")
            lines.append(f"| `{r['instance_id']}` | only in {side} | — | — | — | — | — | — | — |")
            continue
        a, b = r["path_a"], r["path_b"]
        lines.append(
            f"| `{r['instance_id']}` "
            f"| {r['resolved_status']} "
            f"| {_fmt_int(a['total_tokens'])} "
            f"| {_fmt_int(b['total_tokens'])} "
            f"| {_fmt_int(r['delta_tokens'])} "
            f"| {_fmt_float(a['wall_seconds'])} "
            f"| {_fmt_float(b['wall_seconds'])} "
            f"| {_delta(a['wall_seconds'], b['wall_seconds'])} "
            f"| {b['tool_call_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------- Entrypoint ----------


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--path-a", required=True, help="Path A run dir (bench_pathF_swebench)")
    ap.add_argument("--path-b", required=True, help="Path B run dir (bench_pathB_swebench)")
    ap.add_argument("--out", help="Output markdown file (default: stdout)")
    ap.add_argument("--json", help="Also write the aggregate as JSON to this path")
    args = ap.parse_args(argv)

    path_a = Path(args.path_a).expanduser().resolve()
    path_b = Path(args.path_b).expanduser().resolve()
    if not path_a.is_dir():
        print(f"[compare] --path-a not a directory: {path_a}", file=sys.stderr)
        return 2
    if not path_b.is_dir():
        print(f"[compare] --path-b not a directory: {path_b}", file=sys.stderr)
        return 2

    rows, agg = compare(path_a, path_b)
    md = render_markdown(rows, agg)

    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md)
        print(f"[compare] wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(md)

    if args.json:
        jp = Path(args.json).expanduser().resolve()
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps({"aggregate": agg, "rows": rows}, indent=2))
        print(f"[compare] wrote JSON {jp}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
