#!/usr/bin/env python3
"""Dump the structure of one bench JSON + find gold/rubric locations.

Run me on Colossus to figure out why build_scoring_bundle.py returned 0 responses.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

BENCH_ROOT = Path.home() / ".forge-oh" / "bench_pathE"
HOME = Path.home()

print("=" * 70)
print("1. Latest 5 bench JSON files:")
print("=" * 70)
files = sorted(BENCH_ROOT.rglob("c*.json"))
for f in files[-5:]:
    print(f"  {f}  ({f.stat().st_size} B)")

if files:
    sample = files[-1]
    print()
    print("=" * 70)
    print(f"2. Full content of newest cell JSON: {sample}")
    print("=" * 70)
    data = json.loads(sample.read_text())
    # Print keys at top level + one result if present
    print(f"Top-level keys: {list(data.keys())}")
    print(f"model_id: {data.get('model_id')!r}")
    print(f"role: {data.get('role')!r}")
    print(f"runtime: {data.get('runtime')!r}")
    results = data.get("results", [])
    print(f"len(results): {len(results)}")
    if results:
        r0 = results[0]
        print(f"  results[0] keys: {list(r0.keys())}")
        print(f"  results[0].task: {r0.get('task')!r}")
        print(f"  results[0].output_tokens: {r0.get('output_tokens')}")
        print(f"  results[0].wall_seconds: {r0.get('wall_seconds')}")
        stripped = r0.get("content_stripped") or ""
        raw = r0.get("content") or ""
        print(f"  results[0].content_stripped len: {len(stripped)}")
        print(f"  results[0].content len: {len(raw)}")
        # Show first 200 chars of whichever is non-empty
        preview = stripped or raw
        print(f"  preview[:400]:\n{preview[:400]}")
    # If no results, maybe the shape is different
    if not results:
        print("  NO results[] — printing full JSON (truncated):")
        print(json.dumps(data, indent=2)[:3000])

print()
print("=" * 70)
print("3. Search for gold/rubric files anywhere under ~/dev/forge-oh:")
print("=" * 70)
for name in ("debug.md", "arch.md", "plan.md", "debug-rubric.md", "arch-rubric.md", "plan-rubric.md",
            "debug_rubric.md", "arch_rubric.md", "plan_rubric.md"):
    for p in (HOME / "dev" / "forge-oh").rglob(name):
        # skip node_modules, .git, .next, .venv
        s = str(p)
        if any(skip in s for skip in ("node_modules", "/.git/", ".next/", ".venv", "__pycache__")):
            continue
        print(f"  {p}")

print()
print("=" * 70)
print("4. Search for gold/rubric files anywhere under ~ (excluding common junk):")
print("=" * 70)
for name in ("debug.md", "arch.md", "debug-rubric.md", "arch-rubric.md", "plan-rubric.md"):
    for p in HOME.rglob(name):
        s = str(p)
        if any(skip in s for skip in ("node_modules", "/.git/", ".next/", ".venv", "__pycache__",
                                       "/.cache/", "/.local/", "/.rustup/", "/.cargo/")):
            continue
        print(f"  {p}")
