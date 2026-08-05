#!/usr/bin/env python3
"""Build the 30-response scoring bundle for Model Council scoring.

Aggregates every cell × task response under ~/.forge-oh/bench_pathE/*_run/
into a single Markdown file that can be dropped into a subagent objective.

Only the LATEST run directory per cell is used (glob sorts lexicographically;
timestamps are YYYYMMDD_HHMMSS so lex-sort == time-sort).

Output: ~/dev/forge-oh/bench/pathE_qwen36_27b/scoring_bundle_<UTC-YYYYMMDD_HHMM>.md
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BENCH_ROOT = Path.home() / ".forge-oh" / "bench_pathE"
OUT_DIR = Path.home() / "dev" / "forge-oh" / "bench" / "pathE_qwen36_27b"
GOLD_DIR = OUT_DIR / "gold"
RUBRIC_DIR = OUT_DIR / "gold"  # rubrics also live here per session notes

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

CELL_ORDER = ["c01", "c02", "c03", "c03b", "c04", "c05", "c08", "c09", "c11", "c12a", "c12b"]


def latest_per_cell() -> dict[str, Path]:
    """For every cell_id in CELL_ORDER, find the newest json under any run dir."""
    latest: dict[str, tuple[str, Path]] = {}
    for run_dir in sorted(BENCH_ROOT.glob("*_run")):
        run_ts = run_dir.name  # sortable lex == time
        for jf in run_dir.glob("c*.json"):
            # cell id is filename up to first _ after cNN prefix (e.g. c03b_coder_vllm_...)
            stem = jf.stem
            # match c12a, c12b, c03b, c01 etc — one or two digits + optional letter
            m = re.match(r"^(c\d{1,2}[a-z]?)_", stem)
            if not m:
                continue
            cid = m.group(1)
            if cid not in CELL_ORDER:
                continue
            prev = latest.get(cid)
            if prev is None or run_ts > prev[0]:
                latest[cid] = (run_ts, jf)
    return {cid: p for cid, (_, p) in latest.items()}


def load_gold() -> dict[str, str]:
    golds = {}
    for task in ("debug", "arch", "plan"):
        p = GOLD_DIR / f"{task}.md"
        golds[task] = p.read_text() if p.exists() else f"[gold/{task}.md MISSING]"
    return golds


def load_rubric() -> dict[str, str]:
    rubrics = {}
    for task in ("debug", "arch", "plan"):
        for candidate in (RUBRIC_DIR / f"{task}-rubric.md", RUBRIC_DIR / f"{task}_rubric.md"):
            if candidate.exists():
                rubrics[task] = candidate.read_text()
                break
        else:
            rubrics[task] = f"[{task} rubric MISSING]"
    return rubrics


def strip_and_truncate(raw: str, limit: int = 12000) -> str:
    stripped = THINK_RE.sub("", raw or "").strip()
    if len(stripped) > limit:
        stripped = stripped[:limit] + f"\n\n[... truncated at {limit} chars; full content in JSON]"
    return stripped


def main() -> None:
    latest = latest_per_cell()
    missing = [c for c in CELL_ORDER if c not in latest]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"scoring_bundle_{ts}.md"

    lines: list[str] = []
    lines.append(f"# Scoring Bundle — {ts} UTC")
    lines.append("")
    lines.append(f"Cells present: {len(latest)}/{len(CELL_ORDER)}")
    lines.append(f"Cells missing: {missing or '(none)'}")
    lines.append("")

    golds = load_gold()
    rubrics = load_rubric()

    # Golds first
    lines.append("## Gold Answers")
    for task in ("debug", "arch", "plan"):
        lines.append(f"### GOLD — {task}")
        lines.append("")
        lines.append(golds[task])
        lines.append("")

    lines.append("## Rubrics")
    for task in ("debug", "arch", "plan"):
        lines.append(f"### RUBRIC — {task}")
        lines.append("")
        lines.append(rubrics[task])
        lines.append("")

    lines.append("## Cell Responses")
    total = 0
    for cid in CELL_ORDER:
        jf = latest.get(cid)
        if jf is None:
            continue
        data = json.loads(jf.read_text())
        model_id = data.get("model_id", "?")
        runtime = data.get("runtime", "?")
        role = data.get("role", "?")
        lines.append(f"### CELL {cid} — model={model_id} runtime={runtime} role={role}")
        lines.append(f"Source: `{jf}`")
        lines.append("")
        for r in data.get("results", []):
            task = r.get("task", "?")
            if "error" in r:
                lines.append(f"#### {cid} / {task} — ERROR")
                lines.append(f"```\n{r['error']}\n```")
                lines.append("")
                continue
            tok_s = r.get("tok_per_s", 0)
            out_t = r.get("output_tokens", 0)
            wall = r.get("wall_seconds", 0)
            lines.append(f"#### {cid} / {task} — tok/s={tok_s} out={out_t} wall={wall}s")
            lines.append("")
            lines.append(strip_and_truncate(r.get("content_stripped") or r.get("content", "")))
            lines.append("")
            total += 1

    out.write_text("\n".join(lines))
    size_kb = out.stat().st_size // 1024
    print(f"Wrote {out}")
    print(f"Cells: {len(latest)}/{len(CELL_ORDER)}  Responses: {total}  Size: {size_kb} KB")
    if missing:
        print(f"WARNING missing cells: {missing}")


if __name__ == "__main__":
    main()
