#!/usr/bin/env python3
"""F.3 Path A shakeout — SWE-bench Verified pass@1 on raw c01 (oracle-retrieval).

See bench/pathF_swebench/README.md for scope, mode rationale, and gates.

Bench methodology (carried forward from Path E/F):
- Prompts on disk (task JSON here, per-task).
- One output JSON per task.
- <think>...</think> stripped before dump.
- Wall-time + tokens captured (both output_tokens and wall_seconds).
- Quality-first, speed-second — but at this benchmark scale, pass@1 IS quality.

This slice ships two runnable modes:
  --dry-plan-only : task load + oracle prompt build + vLLM call + JSON emit
                    (no docker). Exercises everything except apply_and_test.
  (default)       : full path — requires docker apply_and_test glue that
                    lands in a follow-up slice. Raises NotImplementedError
                    with instructions until the follow-up slice merges.

Usage
-----
    # F.3.0 dry-run (one task, no docker):
    python -m bench.pathF_swebench.bench_pathF_swebench \\
        --tasks django__django-10914 --model c01 --dry-plan-only

    # F.3.0 full dry-run (one task, with docker — requires follow-up slice):
    python -m bench.pathF_swebench.bench_pathF_swebench \\
        --tasks django__django-10914 --model c01

    # F.3.1 full 500 (only after F.3.0 passes):
    python -m bench.pathF_swebench.bench_pathF_swebench \\
        --tasks all --model c01 --concurrency 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urlerr, request as urlreq

# Import guards: this module runs from repo root under -m so relative imports work.
from bench.pathF_swebench.load_verified import dump_task_summary, load_tasks
from bench.pathF_swebench.oracle_prompt import (
    build_prompt,
    files_touched_by_patch,
    read_files_at_commit,
)


REPO = Path.home() / "dev" / "forge-oh"
BENCH_ROOT = Path.home() / ".forge-oh" / "bench_pathF_swebench"
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# Model cells recognized by this harness. F.3 Path A tests c01 only.
# c11 and c03b are included as optional comparators for ADR-013 amendment #2
# defensibility (same shortlist as F.1b).
CELLS: dict[str, dict] = {
    "c01": {
        "endpoint": "http://localhost:8000/v1",
        "model_id": "c01_coder_vllm_qwen36_27b_int4",
        "sampling": {
            "temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
            "presence_penalty": 1.0, "repetition_penalty": 1.05,
        },
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    "c11": {
        "endpoint": "http://localhost:8000/v1",
        "model_id": "c11_coder_vllm_devstral24b_awq",
        "sampling": {
            "temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
            "presence_penalty": 1.0, "repetition_penalty": 1.05,
        },
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    "c03b": {
        "endpoint": "http://localhost:8000/v1",
        "model_id": "c03b_coder_vllm_qwen3coder_awq",
        "sampling": {
            "temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
            "presence_penalty": 1.0, "repetition_penalty": 1.05,
        },
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
}

MAX_TOKENS = 4096  # coder role
REQUEST_TIMEOUT_S = 900  # 15 min per task — plenty for c01 at ~85 tok/s

# ---------- vLLM call ----------


def http_post_json(url: str, payload: dict, timeout: int) -> tuple[dict, float]:
    body = json.dumps(payload).encode()
    req = urlreq.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urlreq.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except urlerr.HTTPError as e:
        return {"error": f"HTTPError {e.code}: {e.read().decode(errors='ignore')}"}, time.time() - t0
    except urlerr.URLError as e:
        return {"error": f"URLError: {e.reason}"}, time.time() - t0
    return data, time.time() - t0


def call_model(cell: dict, prompt: str) -> dict:
    payload = {
        "model": cell["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": MAX_TOKENS,
        **cell["sampling"],
        **cell["extra_body"],
    }
    resp, wall = http_post_json(f"{cell['endpoint']}/chat/completions", payload, REQUEST_TIMEOUT_S)
    if "error" in resp:
        return {"error": resp["error"], "wall_seconds": round(wall, 2)}
    raw = resp["choices"][0]["message"]["content"]
    stripped = THINK_RE.sub("", raw).strip()
    usage = resp.get("usage", {})
    out_toks = usage.get("completion_tokens", 0)
    prompt_toks = usage.get("prompt_tokens", 0)
    tok_per_s = (out_toks / wall) if wall > 0 and out_toks else 0.0
    return {
        "wall_seconds": round(wall, 2),
        "prompt_tokens": prompt_toks,
        "completion_tokens": out_toks,
        "tok_per_s": round(tok_per_s, 2),
        "content_raw": raw,
        "content_raw_chars": len(raw),
        "content_stripped": stripped,
        "content_stripped_chars": len(stripped),
    }


# ---------- repo prep ----------


def _repo_checkout_path(task: dict) -> Path:
    """Local checkout of the task's repo at base_commit, for oracle-file reads.

    We cache one shallow bare checkout per (repo, base_commit) under
    ~/.forge-oh/bench_pathF_swebench/repos/<repo_owner>__<repo_name>__<sha12>/
    Cached forever — same commit always yields the same files.
    """
    owner_name = task["repo"].replace("/", "__")
    sha12 = task["base_commit"][:12]
    out = BENCH_ROOT / "repos" / f"{owner_name}__{sha12}"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [repo prep] cloning {task['repo']} @ {sha12}...", flush=True)
    subprocess.check_call(
        ["git", "clone", "--quiet", f"https://github.com/{task['repo']}.git", str(out)],
    )
    subprocess.check_call(
        ["git", "checkout", "--quiet", task["base_commit"]],
        cwd=out,
    )
    return out


# ---------- one task ----------


def run_task(task: dict, cell_key: str, out_dir: Path, dry_plan_only: bool, keep_sandbox: bool) -> dict:
    cell = CELLS[cell_key]
    instance_id = task["instance_id"]
    print(f"[task] {dump_task_summary(task)}", flush=True)

    # 1. Determine oracle files from ground-truth patch.
    files = files_touched_by_patch(task["patch"])
    print(f"  oracle files: {files}", flush=True)

    # 2. Check out the repo at base_commit and read files.
    repo_root = _repo_checkout_path(task)
    file_contents = read_files_at_commit(repo_root, task["base_commit"], files)

    # 3. Build the oracle-retrieval prompt.
    prompt = build_prompt(task, file_contents)

    # 4. Call the model.
    print(f"  calling {cell['model_id']}...", flush=True)
    model_out = call_model(cell, prompt)
    if "error" in model_out:
        print(f"  ERROR: {model_out['error']}", flush=True)
        return {
            "instance_id": instance_id, "model_id": cell["model_id"],
            "mode": "oracle-retrieval", "phase": "model_call",
            "error": model_out["error"],
            "wall_seconds": model_out.get("wall_seconds", 0),
            "prompt_chars": len(prompt), "oracle_files": files,
        }

    # 5. Extract the patch from the model output (whole content is the diff).
    patch_text = model_out["content_stripped"]

    # 6. Apply patch inside the SWE-bench sandbox and run tests.
    result_payload: dict = {}
    if dry_plan_only:
        result_payload = {"resolved": None, "phase": "dry-plan-only-skipped-docker"}
    else:
        # Deferred until docker glue lands.
        from bench.pathF_swebench.apply_and_test import apply_patch_and_run_tests
        try:
            test_result = apply_patch_and_run_tests(
                instance_id=instance_id,
                patch=patch_text,
                fail_to_pass=task.get("FAIL_TO_PASS", []) or [],
                pass_to_pass=task.get("PASS_TO_PASS", []) or [],
                keep_sandbox=keep_sandbox,
            )
            result_payload = {
                "resolved": test_result.resolved,
                "fail_to_pass_output": test_result.fail_to_pass_output,
                "pass_to_pass_output": test_result.pass_to_pass_output,
                "error": test_result.error,
            }
        except NotImplementedError as e:
            result_payload = {"resolved": None, "phase": "apply_and_test_stub", "error": str(e)}

    task_record = {
        "instance_id": instance_id,
        "model_id": cell["model_id"],
        "mode": "oracle-retrieval",
        "wall_seconds": model_out["wall_seconds"],
        "prompt_tokens": model_out["prompt_tokens"],
        "completion_tokens": model_out["completion_tokens"],
        "tok_per_s": model_out["tok_per_s"],
        "content_raw_chars": model_out["content_raw_chars"],
        "content_stripped_chars": model_out["content_stripped_chars"],
        "patch": patch_text,
        "oracle_files": files,
        "fail_to_pass": task.get("FAIL_TO_PASS", []) or [],
        "pass_to_pass": task.get("PASS_TO_PASS", []) or [],
        **result_payload,
    }

    out_file = out_dir / f"{instance_id}.json"
    out_file.write_text(json.dumps(task_record, indent=2))
    print(
        f"  ok  wall={model_out['wall_seconds']}s "
        f"toks={model_out['completion_tokens']} "
        f"resolved={result_payload.get('resolved')}",
        flush=True,
    )
    return task_record


# ---------- entrypoint ----------


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tasks", required=True, help="instance_id, comma-separated list, or 'all'")
    ap.add_argument("--model", choices=list(CELLS.keys()), default="c01",
                    help="model cell to test (default: c01, the ratified coder)")
    ap.add_argument("--dry-plan-only", action="store_true",
                    help="skip docker apply_and_test; exercise everything else")
    ap.add_argument("--keep-sandbox", action="store_true",
                    help="don't rm sandbox container after test run (debug)")
    args = ap.parse_args(argv)

    # Resolve task list.
    if args.tasks == "all":
        ids: list[str] = ["all"]
    else:
        ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
    tasks = load_tasks(ids)
    print(f"[F.3 Path A] resolved {len(tasks)} task(s); model={args.model}; "
          f"dry_plan_only={args.dry_plan_only}", flush=True)

    # Prepare output dir.
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = BENCH_ROOT / f"{ts}_run"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Manifest.
    manifest = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "ts_local": ts,
        "cell": args.model,
        "model_id": CELLS[args.model]["model_id"],
        "endpoint": CELLS[args.model]["endpoint"],
        "mode": "oracle-retrieval",
        "task_count": len(tasks),
        "task_ids": [t["instance_id"] for t in tasks],
        "dry_plan_only": args.dry_plan_only,
        "keep_sandbox": args.keep_sandbox,
    }
    try:
        manifest["git_sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        manifest["git_sha"] = "unknown"
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Run.
    records: list[dict] = []
    t0 = time.time()
    for task in tasks:
        try:
            rec = run_task(task, args.model, out_dir, args.dry_plan_only, args.keep_sandbox)
            records.append(rec)
        except KeyboardInterrupt:
            print("[F.3 Path A] interrupted; partial results in", out_dir, flush=True)
            return 130
        except Exception as e:
            print(f"[F.3 Path A] task {task['instance_id']} failed: {type(e).__name__}: {e}", flush=True)
            records.append({"instance_id": task["instance_id"], "phase": "harness_error", "error": f"{type(e).__name__}: {e}"})

    total_wall = time.time() - t0

    # Summary.
    resolved = [r for r in records if r.get("resolved") is True]
    unresolved = [r for r in records if r.get("resolved") is False]
    unknown = [r for r in records if r.get("resolved") is None]
    errors = [r for r in records if "error" in r]
    walls = [r["wall_seconds"] for r in records if isinstance(r.get("wall_seconds"), (int, float))]
    summary = {
        "task_count": len(records),
        "resolved_true": len(resolved),
        "resolved_false": len(unresolved),
        "resolved_unknown_or_stubbed": len(unknown),
        "errors": len(errors),
        "pass_at_1": (len(resolved) / len(records)) if records else 0.0,
        "wall_total_s": round(total_wall, 2),
        "wall_median_per_task_s": round(statistics.median(walls), 2) if walls else 0.0,
        "wall_mean_per_task_s": round(statistics.mean(walls), 2) if walls else 0.0,
        "estimated_full_500_wall_hours": round((statistics.mean(walls) * 500 / 3600), 2) if walls else 0.0,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("[F.3 Path A] done. summary:", json.dumps(summary, indent=2), sep="\n")
    print("[F.3 Path A] artifacts:", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
