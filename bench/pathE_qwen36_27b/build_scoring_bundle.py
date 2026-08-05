#!/usr/bin/env python3
"""Build the Model Council scoring bundle for pathE.

Reads the F.19-pre bench JSON shape from ~/.forge-oh/bench_pathE:
  - One file per (cell, task) pair, filename c<NN>[a-z]?__<task>.json
  - Top-level keys: cell, role, runtime, model, profile, runs, latency_*,
    completion_tokens, prompt_tokens, tokens_per_s_med, finish_reason,
    content_raw, content_stripped, prompt_wall_s, ...

Emits one markdown bundle under bench/pathE_qwen36_27b/scoring/ containing:
  - Rubrics (debug, arch, plan)
  - Gold answers (debug, arch, plan)
  - All (cell, task) response blocks with timing metrics
  - Blank score tables per rubric dimension, per (cell, task)

Usage:  python3 bench/pathE_qwen36_27b/build_scoring_bundle.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parents[2]
PATH_E = REPO / "bench" / "pathE_qwen36_27b"
BENCH_ROOT = Path.home() / ".forge-oh" / "bench_pathE"
GOLD = PATH_E / "gold"
OUT_DIR = PATH_E / "scoring"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M")
OUT = OUT_DIR / f"scoring_bundle_{TS}.md"

TASKS = ["debug", "arch", "plan"]
# Coder cells: score debug + arch. Planner cells: score plan.
CODER_CELLS = {"c01", "c02", "c03", "c03b", "c09", "c11", "c12a"}
PLANNER_CELLS = {"c04", "c05", "c08", "c12b"}
# Cell filename pattern: c<NN>[a-z]?__<task>.json
CELL_TASK_RE = re.compile(r"^(c\d+[a-z]?)__(debug|arch|plan)\.json$")


def load_gold(task: str) -> str:
    p = GOLD / f"{task}.md"
    return p.read_text() if p.exists() else f"⚠️ MISSING GOLD: {p}\n"


def load_rubric(task: str) -> str:
    p = GOLD / f"{task}-rubric.md"
    return p.read_text() if p.exists() else f"⚠️ MISSING RUBRIC: {p}\n"


def collect_responses() -> List[Dict]:
    """Return list of dicts: one per (cell, task) response.

    Latest run per (cell, task) wins if multiple runs exist.
    """
    # Map (cell, task) -> (mtime, path)
    latest: Dict[Tuple[str, str], Tuple[float, Path]] = {}
    for jf in BENCH_ROOT.rglob("c*.json"):
        m = CELL_TASK_RE.match(jf.name)
        if not m:
            continue
        cell, task = m.group(1), m.group(2)
        mt = jf.stat().st_mtime
        prev = latest.get((cell, task))
        if prev is None or mt > prev[0]:
            latest[(cell, task)] = (mt, jf)

    records = []
    for (cell, task), (_mt, jf) in sorted(latest.items()):
        try:
            data = json.loads(jf.read_text())
        except Exception as e:
            records.append({
                "cell": cell, "task": task, "error": f"parse failure: {e}",
                "path": str(jf),
            })
            continue
        content = (data.get("content_stripped") or data.get("content_raw") or "").strip()
        records.append({
            "cell": cell,
            "task": task,
            "role": data.get("role", "?"),
            "runtime": data.get("runtime", "?"),
            "model": data.get("model", "?"),
            "profile": data.get("profile", "?"),
            "latency_med_s": data.get("latency_med_s", 0.0),
            "latency_min_s": data.get("latency_min_s", 0.0),
            "latency_max_s": data.get("latency_max_s", 0.0),
            "completion_tokens": data.get("completion_tokens", 0),
            "prompt_tokens": data.get("prompt_tokens", 0),
            "tokens_per_s_med": data.get("tokens_per_s_med", 0.0),
            "finish_reason": data.get("finish_reason", "?"),
            "content": content,
            "content_chars": len(content),
            "path": str(jf),
        })
    return records


def render_block(r: Dict) -> str:
    if "error" in r:
        return (
            f"### {r['cell']} / {r['task']} — PARSE ERROR\n\n"
            f"- Path: `{r['path']}`\n- Error: {r['error']}\n\n---\n"
        )
    header = (
        f"### {r['cell']} / {r['task']}\n\n"
        f"- **Runtime:** {r['runtime']}  \n"
        f"- **Role:** {r['role']} ({r['profile']})  \n"
        f"- **Model ID:** `{r['model']}`  \n"
        f"- **Latency (med / min / max):** {r['latency_med_s']:.2f}s / "
        f"{r['latency_min_s']:.2f}s / {r['latency_max_s']:.2f}s  \n"
        f"- **Tokens (prompt / completion):** {r['prompt_tokens']} / {r['completion_tokens']}  \n"
        f"- **Throughput:** {r['tokens_per_s_med']:.2f} tok/s (med)  \n"
        f"- **Finish:** {r['finish_reason']}  \n"
        f"- **Output size:** {r['content_chars']} chars\n\n"
    )
    body = f"**Response:**\n\n```\n{r['content']}\n```\n\n---\n"
    return header + body


def render_score_table(records: List[Dict]) -> str:
    """Emit blank score tables grouped by task, for the council to fill in."""
    out = []
    out.append("# Score Tables (fill in during Council pass)\n\n")

    for task in TASKS:
        rows = [r for r in records if r.get("task") == task and "error" not in r]
        if not rows:
            continue
        # Filter: only score coder cells on debug/arch, planner cells on plan
        if task in ("debug", "arch"):
            rows = [r for r in rows if r["cell"] in CODER_CELLS]
        else:  # plan
            rows = [r for r in rows if r["cell"] in PLANNER_CELLS]
        if not rows:
            continue

        rubric = f"gold/{task}-rubric.md"
        out.append(f"## Task: `{task}`  (rubric: `{rubric}`)\n\n")
        # Column count depends on task rubric dimensions; keep it generic
        if task == "debug":
            headers = ["Cell", "A (25) RootCause", "B (40) FixCorrect",
                       "C (20) CmdPrecision", "D (10) Verify", "E (5) Rules",
                       "TOTAL", "Notes"]
        elif task == "arch":
            headers = ["Cell", "A (30) Decision", "B (25) Justif",
                       "C (15) Grep", "D (15) Sed", "E (10) Convention",
                       "F (5) Format", "TOTAL", "Notes"]
        else:  # plan
            headers = ["Cell", "A (30) Contract", "B (25) Sequence",
                       "C (15) Paths", "D (10) Commits", "E (10) Verify",
                       "F (10) Scope", "TOTAL", "Notes"]

        out.append("| " + " | ".join(headers) + " |\n")
        out.append("|" + "|".join(["---"] * len(headers)) + "|\n")
        for r in rows:
            out.append(f"| {r['cell']} " + "| " * (len(headers) - 1) + "|\n")
        out.append("\n")

    out.append("## Timing Roll-Up (informational)\n\n")
    out.append("| Cell | Task | Role | Latency med (s) | tok/s med | Tokens out |\n")
    out.append("|---|---|---|---:|---:|---:|\n")
    for r in records:
        if "error" in r:
            continue
        out.append(
            f"| {r['cell']} | {r['task']} | {r['role']} | "
            f"{r['latency_med_s']:.2f} | {r['tokens_per_s_med']:.2f} | "
            f"{r['completion_tokens']} |\n"
        )
    out.append("\n")
    return "".join(out)


def main() -> None:
    records = collect_responses()
    if not records:
        raise SystemExit(f"No bench JSON found under {BENCH_ROOT}")

    lines = []
    lines.append(f"# Model Council Scoring Bundle — pathE\n\n")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
    lines.append(f"Bench root: `{BENCH_ROOT}`\n\n")
    lines.append(f"Response count: **{len(records)}** across {len(TASKS)} tasks\n\n")

    coder_present = sorted({r['cell'] for r in records if r.get('task') in ('debug', 'arch') and 'error' not in r})
    planner_present = sorted({r['cell'] for r in records if r.get('task') == 'plan' and 'error' not in r})
    lines.append(f"- Coder cells with debug/arch responses: {coder_present}\n")
    lines.append(f"- Planner cells with plan responses: {planner_present}\n\n")

    lines.append("---\n\n# Rubrics\n\n")
    for task in TASKS:
        lines.append(f"## Rubric: {task}\n\n")
        lines.append(load_rubric(task))
        lines.append("\n---\n\n")

    lines.append("# Gold Answers\n\n")
    for task in TASKS:
        lines.append(f"## Gold: {task}\n\n")
        lines.append(load_gold(task))
        lines.append("\n---\n\n")

    lines.append("# Responses\n\n")
    for task in TASKS:
        task_recs = sorted([r for r in records if r.get('task') == task],
                           key=lambda x: x['cell'])
        if not task_recs:
            continue
        lines.append(f"## Task: {task}  ({len(task_recs)} responses)\n\n")
        for r in task_recs:
            lines.append(render_block(r))
        lines.append("\n")

    lines.append("---\n\n")
    lines.append(render_score_table(records))

    OUT.write_text("".join(lines))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(records)} responses)")


if __name__ == "__main__":
    main()
