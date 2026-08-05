"""SWE-bench Verified loader — pulls tasks from `princeton-nlp/SWE-bench_Verified`.

Cached in HF's default cache dir on first use. Filters exposed for the
dry-run (single instance_id) and full-run (all 500) paths.

Task dict shape (fields we care about):
- instance_id: str, e.g. "django__django-10914"
- problem_statement: str, the GitHub issue body
- repo: str, e.g. "django/django"
- base_commit: str, git SHA the sandbox image is built at
- FAIL_TO_PASS: list[str], test IDs that must go RED→GREEN
- PASS_TO_PASS: list[str], test IDs that must stay GREEN
- patch: str, ground-truth patch (used to derive oracle files)
- test_patch: str, test additions
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Iterable


DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
SPLIT = "test"


@lru_cache(maxsize=1)
def _load_full():
    """Load the full Verified split once per process."""
    # Deferred import so `--help` works without HF datasets installed.
    from datasets import load_dataset  # type: ignore
    ds = load_dataset(DATASET_NAME, split=SPLIT)
    return list(ds)


def load_tasks(instance_ids: Iterable[str] | None = None) -> list[dict]:
    """Return tasks by instance_id. Pass None (or ('all',)) to get all 500."""
    tasks = _load_full()
    if instance_ids is None:
        return tasks
    ids = list(instance_ids)
    if ids == ["all"]:
        return tasks
    wanted = set(ids)
    hit = [t for t in tasks if t["instance_id"] in wanted]
    miss = wanted - {t["instance_id"] for t in hit}
    if miss:
        raise ValueError(f"Verified split has no such instance_ids: {sorted(miss)}")
    return hit


def dump_task_summary(task: dict) -> str:
    """Compact one-line summary for logging."""
    return (
        f"{task['instance_id']}  repo={task['repo']}  "
        f"base={task['base_commit'][:12]}  "
        f"F2P={len(task.get('FAIL_TO_PASS', []) or [])}  "
        f"P2P={len(task.get('PASS_TO_PASS', []) or [])}"
    )


if __name__ == "__main__":
    # Smoke test: `python -m bench.pathF_swebench.load_verified`
    tasks = load_tasks(["django__django-10914"])
    print(json.dumps({"count": len(tasks), "summary": dump_task_summary(tasks[0])}, indent=2))
