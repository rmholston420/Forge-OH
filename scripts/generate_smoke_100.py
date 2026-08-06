"""Generate SMOKE_100_TASK_IDS by extending SMOKE_TASK_IDS with 70 more tasks
stratified from the F.3 full-500 ground-truth run.

Slice 8.0.5 (measurement hardening). Council-Synthesis line 117:
"expand smoke set toward ≥100 tasks."

Reproduces the same stratification recipe used for the original 30-task set
(described in bench/pathF_swebench/bench_pathF_swebench.py lines 163-176):

  1. Load the full-500 ground-truth outcomes from a completed F.3 run.
  2. Bucket tasks by repo × outcome (resolved / unresolved / context-budget-skip).
  3. For each repo, allocate a quota proportional to that repo's share of the
     full-500 (rounded); within each repo, keep the ratio of outcome buckets.
  4. Sample within each (repo, outcome) bucket with random.seed(42), the same
     seed the 30-task set used, so the first 30 IDs come out identical to the
     existing SMOKE_TASK_IDS.

Design constraints:
  - The first 30 IDs of the output MUST equal the current SMOKE_TASK_IDS in the
    same order (regression: attestations against the original 30-task set stay
    directly comparable to the smoke-100 prefix).
  - Extension of 70 tasks brings the total to 100.

Usage (on Colossus):
  cd ~/dev/forge-oh
  python3 scripts/generate_smoke_100.py \\
      ~/.forge-oh/bench_pathF_swebench/20260805_1025_run/

Writes the generated list to stdout as a Python literal that can be pasted into
bench/pathF_swebench/bench_pathF_swebench.py.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path


# The 30-task ordering used by SMOKE_TASK_IDS in bench_pathF_swebench.py.
# The generator must produce these as its first 30 entries when TARGET_TOTAL=30.
CURRENT_SMOKE_30 = [
    "django__django-11099", "django__django-11749", "django__django-11880",
    "django__django-11999", "django__django-12308", "django__django-13401",
    "django__django-13512", "django__django-13925", "django__django-15629",
    "django__django-16333", "django__django-16801",
    "sympy__sympy-12096", "sympy__sympy-13031", "sympy__sympy-13878",
    "sympy__sympy-14248", "sympy__sympy-14711",
    "sphinx-doc__sphinx-7590", "sphinx-doc__sphinx-8548", "sphinx-doc__sphinx-9591",
    "matplotlib__matplotlib-24570", "matplotlib__matplotlib-26208",
    "scikit-learn__scikit-learn-13142", "scikit-learn__scikit-learn-14629",
    "pydata__xarray-4687", "astropy__astropy-14365",
    "pytest-dev__pytest-10356", "pylint-dev__pylint-4661",
    "psf__requests-6028", "mwaskom__seaborn-3187", "pallets__flask-5014",
]
TARGET_TOTAL = 100
SEED = 42


def _load_full_run(run_dir: Path) -> list[dict]:
    """Load all per-task JSONs from an F.3 full-500 run dir.

    Returns list of dicts with fields: instance_id, repo, outcome.
    outcome is one of: 'resolved', 'unresolved', 'context_skip', 'error'.
    """
    records = []
    for p in sorted(run_dir.glob("*.json")):
        if p.name in ("manifest.json", "summary.json", "progress.json"):
            continue
        if p.name.startswith("manifest_") or p.name.startswith("pair_comparison"):
            continue
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        inst = r.get("instance_id")
        if not inst:
            continue
        # Repo prefix, e.g. "django__django-11099" -> "django/django"
        # Follow the SWE-bench Verified instance_id convention: "<org>__<repo>-<n>"
        repo_key = inst.split("-")[0].replace("__", "/", 1)
        if r.get("context_budget_skipped"):
            outcome = "context_skip"
        elif "error" in r:
            outcome = "error"
        elif r.get("resolved") is True:
            outcome = "resolved"
        elif r.get("resolved") is False:
            outcome = "unresolved"
        else:
            outcome = "error"  # unknown / stubbed
        records.append({"instance_id": inst, "repo": repo_key, "outcome": outcome})
    return records


def _bucket(records: list[dict]) -> dict[tuple[str, str], list[str]]:
    """Group records into {(repo, outcome): [instance_id, ...]} buckets."""
    buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in records:
        buckets[(r["repo"], r["outcome"])].append(r["instance_id"])
    # Sort each bucket deterministically before sampling
    for k in buckets:
        buckets[k].sort()
    return buckets


def _stratified_sample(records: list[dict], n_target: int) -> list[str]:
    """Draw n_target instance_ids stratified by repo × outcome.

    Repo quota is proportional to repo share of the full-500 (rounded up so
    every repo with ≥1 task in full-500 gets at least 1 sample). Within a repo,
    outcome quota is proportional to outcome share within that repo.

    Deterministic given SEED.
    """
    rng = random.Random(SEED)
    total = len(records)
    if total == 0:
        return []
    repo_counts: dict[str, int] = defaultdict(int)
    for r in records:
        repo_counts[r["repo"]] += 1

    # Compute per-repo quota
    repo_quotas: dict[str, int] = {}
    for repo, cnt in repo_counts.items():
        # Proportional, rounded to nearest, minimum 1 if repo has any tasks
        raw = n_target * (cnt / total)
        repo_quotas[repo] = max(1, round(raw))

    # Adjust so repo_quotas sums to exactly n_target
    diff = n_target - sum(repo_quotas.values())
    # If quotas are over/under, adjust the largest repos first (they had the
    # most rounding to absorb).
    sorted_repos = sorted(repo_quotas, key=lambda r: -repo_counts[r])
    idx = 0
    while diff != 0 and idx < len(sorted_repos) * 4:
        repo = sorted_repos[idx % len(sorted_repos)]
        if diff > 0:
            repo_quotas[repo] += 1
            diff -= 1
        elif repo_quotas[repo] > 1:
            repo_quotas[repo] -= 1
            diff += 1
        idx += 1

    buckets = _bucket(records)
    sampled: list[str] = []
    for repo in sorted(repo_quotas):
        repo_records = [r for r in records if r["repo"] == repo]
        repo_total = len(repo_records)
        outcome_counts: dict[str, int] = defaultdict(int)
        for r in repo_records:
            outcome_counts[r["outcome"]] += 1
        # Outcome quota within the repo, min 1 for each present outcome
        outcome_quotas: dict[str, int] = {}
        for outcome, cnt in outcome_counts.items():
            raw = repo_quotas[repo] * (cnt / repo_total)
            outcome_quotas[outcome] = max(1, round(raw))
        # Rebalance outcome quotas to sum to repo quota
        odiff = repo_quotas[repo] - sum(outcome_quotas.values())
        sorted_outcomes = sorted(outcome_quotas, key=lambda o: -outcome_counts[o])
        oidx = 0
        while odiff != 0 and oidx < len(sorted_outcomes) * 4:
            o = sorted_outcomes[oidx % len(sorted_outcomes)]
            if odiff > 0:
                outcome_quotas[o] += 1
                odiff -= 1
            elif outcome_quotas[o] > 1:
                outcome_quotas[o] -= 1
                odiff += 1
            oidx += 1
        # Sample within each (repo, outcome) bucket
        for outcome, quota in sorted(outcome_quotas.items()):
            bucket = buckets[(repo, outcome)][:]
            # Cap at bucket size (can't sample more than we have)
            k = min(quota, len(bucket))
            sampled.extend(rng.sample(bucket, k))
    return sampled


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <full_500_run_dir>", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 2

    records = _load_full_run(run_dir)
    if not records:
        print(f"no per-task JSONs found in {run_dir}", file=sys.stderr)
        return 2
    print(f"# loaded {len(records)} task records from {run_dir}",
          file=sys.stderr)

    # First, verify we can reproduce the existing 30-task set.
    reproduced_30 = _stratified_sample(records, 30)
    reproduced_set = set(reproduced_30)
    current_set = set(CURRENT_SMOKE_30)
    if reproduced_set != current_set:
        missing = current_set - reproduced_set
        extra = reproduced_set - current_set
        print(f"# WARNING: 30-task reproduction differs from CURRENT_SMOKE_30",
              file=sys.stderr)
        print(f"#   missing from reproduced: {sorted(missing)[:5]}",
              file=sys.stderr)
        print(f"#   extra in reproduced:     {sorted(extra)[:5]}",
              file=sys.stderr)
        print(f"# proceeding with a UNION approach: keep the current 30 verbatim,",
              file=sys.stderr)
        print(f"# then sample the additional 70 from tasks not in the 30.",
              file=sys.stderr)

    # Extend to 100. Approach: keep CURRENT_SMOKE_30 as the prefix, then sample
    # 70 more from the pool of full-500 tasks EXCLUDING those 30. Use the same
    # stratification recipe on the remaining pool.
    remaining_records = [r for r in records if r["instance_id"] not in current_set]
    extension = _stratified_sample(remaining_records, TARGET_TOTAL - len(CURRENT_SMOKE_30))
    # Sort extension by repo + instance_id for readability
    extension.sort()

    combined = list(CURRENT_SMOKE_30) + extension
    print(f"# generated {len(combined)} instance IDs "
          f"({len(CURRENT_SMOKE_30)} prefix + {len(extension)} extension)",
          file=sys.stderr)

    # Emit as a paste-able Python literal
    print("SMOKE_100_TASK_IDS = [")
    print("    # First 30: verbatim from SMOKE_TASK_IDS (Slice 8.0 baseline)")
    for iid in CURRENT_SMOKE_30:
        print(f'    "{iid}",')
    print("    # Extension (70 tasks) — Slice 8.0.5, seed=42 stratified from")
    print("    # F.3 full-500 minus the 30 above.")
    for iid in extension:
        print(f'    "{iid}",')
    print("]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
