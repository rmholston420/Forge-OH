#!/usr/bin/env python3
"""Build a scoring bundle from Path F run directories.

Dumps content_stripped + metrics for every (cell, prompt) into a single
markdown bundle suitable for pasting into a scoring context (Model
Council rescore).

Usage:
    python -m bench.pathF_instrumented.build_scoring_bundle \\
        --runs ~/.forge-oh/bench_pathF/f1b_c11 \\
               ~/.forge-oh/bench_pathF/f1b_c03b \\
               ~/.forge-oh/bench_pathF/f1b_c01 \\
        --out ~/dev/forge-oh/bench/pathF_instrumented/scoring_bundle_f1b.md
"""
import argparse
import json
import sys
from pathlib import Path


def dump_result(f: Path) -> str:
    d = json.loads(f.read_text())
    if "error" in d:
        return (
            f"\n### {d.get('cell')} / {d.get('profile') or ''} — ERROR\n"
            f"- error: `{d['error'][:400]}`\n"
        )
    gpu = d.get("gpu_aggregate") or {}
    header = (
        f"\n### `{d['cell']}` — `{d['model']}` — prompt: `{f.stem.split('__', 1)[1]}`\n\n"
        f"- role: `{d['role']}` · runtime: `{d['runtime']}` · profile: `{d['profile']}`\n"
        f"- runs: {d['runs']} scored" + (" + warmup" if d.get('warmup') else "") + "\n"
        f"- latency: min={d['latency_min_s']:.2f}s · med={d['latency_med_s']:.2f}s · max={d['latency_max_s']:.2f}s\n"
        f"- tokens: {d['completion_tokens']} completion · {d.get('prompt_tokens', 0)} prompt · **{d['tokens_per_s_med']:.1f} tok/s** (med)\n"
        f"- finish_reason: `{d.get('finish_reason')}`\n"
    )
    if gpu:
        header += (
            f"- gpu envelope:\n"
            f"  - VRAM: avg={gpu.get('vram_avg_mib', 0):.0f} MiB · max={gpu.get('vram_max_mib', 0)} MiB\n"
            f"  - util: avg={gpu.get('gpu_util_avg_pct', 0):.1f}% · max={gpu.get('gpu_util_max_pct', 0)}%\n"
            f"  - temp: avg={gpu.get('gpu_temp_avg_c', 0):.1f}°C · max={gpu.get('gpu_temp_max_c', 0)}°C\n"
            f"  - power: avg={gpu.get('power_avg_w', 0):.1f} W · max={gpu.get('power_max_w', 0):.1f} W\n"
        )
    body = "\n**Output (`content_stripped`, `<think>` blocks removed):**\n\n```\n"
    body += (d.get("content_stripped") or "").strip()
    body += "\n```\n"
    return header + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True,
                    help="run directories (each contains {cell}__{prompt}.json files)")
    ap.add_argument("--out", required=True, help="output markdown file")
    args = ap.parse_args()

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parts = []
    parts.append("# Path F — F.1b Scoring Bundle\n")
    parts.append(f"Generated from {len(args.runs)} run dir(s):\n\n")
    for r in args.runs:
        parts.append(f"- `{r}`\n")
    parts.append("\n---\n")

    for run_dir in args.runs:
        run_dir = Path(run_dir).expanduser().resolve()
        cell_files = sorted(run_dir.glob("*__*.json"))
        if not cell_files:
            print(f"WARN: no cell files in {run_dir}", file=sys.stderr)
            continue
        parts.append(f"\n## Run: `{run_dir}`\n")
        for f in cell_files:
            parts.append(dump_result(f))

    out_path.write_text("".join(parts))
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
