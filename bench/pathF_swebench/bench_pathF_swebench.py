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
from bench.pathF_swebench.apply_and_test import normalize_patch
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

# Context budgeting. vLLM launches c01 with --max-model-len 32768.
# We must satisfy: prompt_tokens + max_tokens <= MAX_MODEL_LEN.
# We dynamically cap max_tokens per request using a live /tokenize probe.
MAX_MODEL_LEN = 32768
MAX_TOKENS_CEILING = 4096   # cap for coder diffs; won't grow past this even if room allows
MAX_TOKENS_FLOOR = 512      # if we can't guarantee at least this much room, skip the task
CONTEXT_SAFETY_MARGIN = 64  # tokenizer + chat-template can add a few tokens; keep some slack
REQUEST_TIMEOUT_S = 900  # 15 min per task — plenty for c01 at ~85 tok/s
GPU_SAMPLE_INTERVAL_S = 0.5  # NVML polling cadence per bench methodology / F.1b

# GPU sampling: mandatory on every bench harness per the module docstring in
# bench/_common/nvml_sampler.py ("All future bench runs must use this sampler").
# Reason: quality + speed alone are misleading when a run is thermally throttled,
# VRAM-pressured, or contending with another CUDA workload.
try:
    from bench._common.nvml_sampler import GpuSampler  # type: ignore
    _GPU_SAMPLER_AVAILABLE = True
except Exception as _e:  # pragma: no cover - import guard
    GpuSampler = None  # type: ignore
    _GPU_SAMPLER_AVAILABLE = False
    print(f"[F.3 Path A] warn: NVML sampler unavailable: {_e}", flush=True)

# 30-task calibrated smoke set (v2) — stratified sample from the F.3 full-500
# ground-truth outcomes (~/.forge-oh/bench_pathF_swebench/20260805_1025_run,
# recorded in ADR-013 amendment #2). Proportional to full-500 repo distribution
# (django=231, sympy=75, sphinx=44, ...) with within-repo stratification by
# outcome (resolved / unresolved / context-budget-skip) using random.seed(42).
#
# Predicted pass@1 = 26.7% raw (Δ = +0.1pt vs full-500's 26.6% raw); this smoke
# is calibrated to predict full-500 within 3pt for regression-testing harness
# changes without a 9-hour full run. Every task listed here has a KNOWN outcome
# from the full-500 log, marked in the comment column.
#
# Composition: 8 resolved + 18 unresolved + 4 context-budget-skip = 30.
# Full 12/12 repo coverage (adds astropy/xarray/pytest/pylint/requests/seaborn/
# flask that were absent in the old 5-repo smoke-25).
SMOKE_TASK_IDS = [
    # django/django (11: 3 resolved + 7 unresolved + 1 skip; largest slice)
    "django__django-11099",       # expected: resolved
    "django__django-11749",       # expected: unresolved
    "django__django-11880",       # expected: unresolved
    "django__django-11999",       # expected: resolved
    "django__django-12308",       # expected: unresolved
    "django__django-13401",       # expected: unresolved
    "django__django-13512",       # expected: unresolved
    "django__django-13925",       # expected: resolved
    "django__django-15629",       # expected: skip
    "django__django-16333",       # expected: unresolved
    "django__django-16801",       # expected: unresolved
    # sympy/sympy (5: 1 resolved + 3 unresolved + 1 skip)
    "sympy__sympy-12096",         # expected: unresolved
    "sympy__sympy-13031",         # expected: unresolved
    "sympy__sympy-13878",         # expected: unresolved
    "sympy__sympy-14248",         # expected: skip
    "sympy__sympy-14711",         # expected: resolved
    # sphinx-doc/sphinx (3: 1 resolved + 1 unresolved + 1 skip)
    "sphinx-doc__sphinx-7590",    # expected: skip
    "sphinx-doc__sphinx-8548",    # expected: unresolved
    "sphinx-doc__sphinx-9591",    # expected: resolved
    # matplotlib/matplotlib (2: 1 resolved + 1 skip — hardest repo, skip-heavy)
    "matplotlib__matplotlib-24570",  # expected: resolved
    "matplotlib__matplotlib-26208",  # expected: skip
    # scikit-learn/scikit-learn (2: 1 resolved + 1 unresolved — strongest repo)
    "scikit-learn__scikit-learn-13142",  # expected: unresolved
    "scikit-learn__scikit-learn-14629",  # expected: resolved
    # pydata/xarray (1 unresolved)
    "pydata__xarray-4687",        # expected: unresolved
    # astropy/astropy (1 unresolved — weakest repo by pass@1)
    "astropy__astropy-14365",     # expected: unresolved
    # pytest-dev/pytest (1 unresolved)
    "pytest-dev__pytest-10356",   # expected: unresolved
    # pylint-dev/pylint (1 unresolved)
    "pylint-dev__pylint-4661",    # expected: unresolved
    # psf/requests (1 unresolved)
    "psf__requests-6028",         # expected: unresolved
    # mwaskom/seaborn (1 unresolved)
    "mwaskom__seaborn-3187",      # expected: unresolved
    # pallets/flask (1 resolved — sole flask task in full-500, resolved cleanly)
    "pallets__flask-5014",        # expected: resolved
]

# Backward-compat alias. Prefer SMOKE_TASK_IDS.
SMOKE_25_TASK_IDS = SMOKE_TASK_IDS

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


def _empty_gpu_stats() -> dict:
    """Placeholder GPU dict when the sampler is unavailable."""
    return {
        "samples": 0,
        "nvml_available": False,
        "sampling_interval_s": GPU_SAMPLE_INTERVAL_S,
        "sampling_wall_s": 0.0,
    }


def _count_prompt_tokens(cell: dict, prompt: str) -> int | None:
    """Ask vLLM to tokenize the prompt via the chat template. Returns token
    count or None if the endpoint doesn't respond (older vLLM without /tokenize).

    NOTE: vLLM's tokenize endpoint lives at BASE `/tokenize`, NOT `/v1/tokenize`
    (per official PR #5054). The cell's `endpoint` is the OpenAI base ending in
    `/v1`, so we strip that suffix here.
    """
    base = cell["endpoint"].rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    url = f"{base}/tokenize"
    payload = {
        "model": cell["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "add_generation_prompt": True,
    }
    resp, _ = http_post_json(url, payload, timeout=60)
    if "error" in resp:
        return None
    # vLLM /tokenize returns {"tokens": [...], "count": N, "max_model_len": ...}
    if "count" in resp and isinstance(resp["count"], int):
        return resp["count"]
    if "tokens" in resp and isinstance(resp["tokens"], list):
        return len(resp["tokens"])
    return None


def budget_max_tokens(prompt_tokens: int) -> tuple[int, str]:
    """Compute a safe max_tokens for a given prompt size.

    Returns (max_tokens, note). max_tokens=0 means the prompt is already so
    large that even MAX_TOKENS_FLOOR won't fit — caller must skip.
    """
    room = MAX_MODEL_LEN - prompt_tokens - CONTEXT_SAFETY_MARGIN
    if room < MAX_TOKENS_FLOOR:
        return 0, f"prompt_tokens={prompt_tokens} leaves only {room}t room (< floor {MAX_TOKENS_FLOOR})"
    if room >= MAX_TOKENS_CEILING:
        return MAX_TOKENS_CEILING, "full ceiling fits"
    return room, f"reduced from ceiling {MAX_TOKENS_CEILING} → {room} due to prompt size"


def call_model(cell: dict, prompt: str, prompt_tokens: int | None = None) -> dict:
    # Dynamic max_tokens budgeting. If /tokenize is available, respect the true
    # count; else fall back to the ceiling and let vLLM 400 with a clear reason.
    if prompt_tokens is None:
        prompt_tokens = _count_prompt_tokens(cell, prompt)
    if prompt_tokens is not None:
        max_tokens, budget_note = budget_max_tokens(prompt_tokens)
        if max_tokens == 0:
            return {
                "error": f"context-budget-skip: {budget_note}",
                "wall_seconds": 0.0,
                "prompt_tokens": prompt_tokens,
                "gpu": _empty_gpu_stats(),
                "context_budget_skipped": True,
            }
    else:
        # No /tokenize available. Trust MAX_TOKENS_CEILING and let a 400 surface
        # if the prompt is oversized. Log so we notice.
        max_tokens = MAX_TOKENS_CEILING
        budget_note = "tokenize-unavailable-using-ceiling"
        print(f"  [warn] /tokenize probe returned no count; using ceiling {MAX_TOKENS_CEILING}", flush=True)
    payload = {
        "model": cell["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        **cell["sampling"],
        **cell["extra_body"],
    }
    # Wrap the vLLM call in an NVML sample window. This is the coder inference
    # window — separate from the docker apply-and-test window.
    sampler = GpuSampler(interval_s=GPU_SAMPLE_INTERVAL_S) if _GPU_SAMPLER_AVAILABLE else None
    if sampler is not None:
        sampler.start()
    try:
        resp, wall = http_post_json(f"{cell['endpoint']}/chat/completions", payload, REQUEST_TIMEOUT_S)
    finally:
        gpu_stats = sampler.stop().to_dict() if sampler is not None else _empty_gpu_stats()
    if "error" in resp:
        return {
            "error": resp["error"],
            "wall_seconds": round(wall, 2),
            "gpu": gpu_stats,
            "max_tokens_requested": max_tokens,
            "budget_note": budget_note,
            "prompt_tokens_pre": prompt_tokens,
        }
    raw = resp["choices"][0]["message"]["content"]
    stripped = THINK_RE.sub("", raw).strip()
    usage = resp.get("usage", {})
    out_toks = usage.get("completion_tokens", 0)
    prompt_toks = usage.get("prompt_tokens", 0)
    tok_per_s = (out_toks / wall) if wall > 0 and out_toks else 0.0
    finish_reason = resp["choices"][0].get("finish_reason")
    truncated_by_length = (finish_reason == "length")
    return {
        "wall_seconds": round(wall, 2),
        "prompt_tokens": prompt_toks,
        "completion_tokens": out_toks,
        "tok_per_s": round(tok_per_s, 2),
        "content_raw": raw,
        "content_raw_chars": len(raw),
        "content_stripped": stripped,
        "content_stripped_chars": len(stripped),
        "gpu": gpu_stats,
        "max_tokens_requested": max_tokens,
        "budget_note": budget_note,
        "finish_reason": finish_reason,
        "truncated_by_length": truncated_by_length,
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


def _fmt_dur(seconds: float) -> str:
    """Compact wall-clock: 3s / 47s / 1m23s / 2h05m."""
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def run_task(
    task: dict,
    cell_key: str,
    out_dir: Path,
    dry_plan_only: bool,
    keep_sandbox: bool,
    task_idx: int,
    task_total: int,
) -> dict:
    cell = CELLS[cell_key]
    instance_id = task["instance_id"]
    print(f"[task {task_idx}/{task_total}] {dump_task_summary(task)}", flush=True)

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
        err_record = {
            "instance_id": instance_id, "model_id": cell["model_id"],
            "task_index": task_idx, "task_total": task_total,
            "mode": "oracle-retrieval", "phase": "model_call",
            "error": model_out["error"],
            "wall_seconds": model_out.get("wall_seconds", 0),
            "prompt_chars": len(prompt), "oracle_files": files,
            "context_budget_skipped": model_out.get("context_budget_skipped", False),
            "budget_note": model_out.get("budget_note"),
            "prompt_tokens_pre": model_out.get("prompt_tokens_pre"),
            "resolved": False,
        }
        (out_dir / f"{instance_id}.json").write_text(json.dumps(err_record, indent=2))
        return err_record

    # 5. Extract the patch from the model output (whole content is the diff).
    #    Strip markdown code fences: some models (c01 confirmed) wrap the diff
    #    in ```diff ... ``` even when instructed not to. git apply rejects fenced text.
    patch_raw = model_out["content_stripped"]
    patch_text = normalize_patch(patch_raw)
    # Track whether recount_hunks() actually rewrote any header so we can
    # tell (post-run) how often the model got hunk math wrong. Cheap: just
    # re-strip fences from raw and compare pre-recount vs post-recount.
    _pre_recount = patch_raw
    # Mirror the fence-strip steps that normalize_patch does, MINUS recount.
    if _pre_recount:
        _pre_recount = _pre_recount.strip()
        import re as _re
        _pre_recount = _re.sub(r"^\s*```(?:diff|patch)?\s*\n", "", _pre_recount, count=1, flags=_re.IGNORECASE)
        _pre_recount = _re.sub(r"\n\s*```\s*$", "", _pre_recount, count=1)
        _pre_recount = _pre_recount.strip()
    patch_recounted = (patch_text != _pre_recount)

    # 6. Apply patch inside the SWE-bench sandbox and run tests via the
    #    official swebench harness (see apply_and_test.py docstring).
    #    Wrap in a SECOND NVML window (`gpu_harness`) — separate from the
    #    inference window — so we can tell if the docker harness ever wakes
    #    the GPU. On Verified this is usually near-zero (pytest, CPU-only),
    #    which is itself the diagnostic signal.
    result_payload: dict = {}
    gpu_harness_stats: dict = _empty_gpu_stats()
    if dry_plan_only:
        result_payload = {"resolved": None, "phase": "dry-plan-only-skipped-docker"}
    else:
        from bench.pathF_swebench.apply_and_test import apply_patch_and_run_tests
        # Give the harness its own dir under the run so its logs/, evaluation_results/
        # don't collide with our per-task JSON.
        swebench_root = out_dir.parent.parent / "swebench_runs"
        swebench_root.mkdir(parents=True, exist_ok=True)
        harness_run_id = f"{out_dir.name}__{instance_id}"
        harness_sampler = GpuSampler(interval_s=GPU_SAMPLE_INTERVAL_S) if _GPU_SAMPLER_AVAILABLE else None
        if harness_sampler is not None:
            harness_sampler.start()
        try:
            test_result = apply_patch_and_run_tests(
                instance_id=instance_id,
                patch=patch_text,
                model_name=cell["model_id"],
                artifacts_root=swebench_root,
                run_id=harness_run_id,
                keep_sandbox=keep_sandbox,
            )
        finally:
            gpu_harness_stats = (
                harness_sampler.stop().to_dict() if harness_sampler is not None else _empty_gpu_stats()
            )
        result_payload = {
            "resolved": test_result.resolved,
            "phase": "swebench-harness",
            "harness_return_code": test_result.harness_return_code,
            "harness_run_id": harness_run_id,
            "harness_artifacts_dir": str(swebench_root / harness_run_id),
            "harness_error": test_result.error,
            "harness_stdout_tail": test_result.stdout_tail,
            "harness_stderr_tail": test_result.stderr_tail,
            "harness_report": test_result.report,
        }

    task_record = {
        "instance_id": instance_id,
        "model_id": cell["model_id"],
        "task_index": task_idx,
        "task_total": task_total,
        "mode": "oracle-retrieval",
        "wall_seconds": model_out["wall_seconds"],
        "prompt_tokens": model_out["prompt_tokens"],
        "completion_tokens": model_out["completion_tokens"],
        "tok_per_s": model_out["tok_per_s"],
        "max_tokens_requested": model_out.get("max_tokens_requested"),
        "budget_note": model_out.get("budget_note"),
        "finish_reason": model_out.get("finish_reason"),
        "truncated_by_length": model_out.get("truncated_by_length", False),
        "content_raw_chars": model_out["content_raw_chars"],
        "content_stripped_chars": model_out["content_stripped_chars"],
        "patch": patch_text,
        "patch_raw": patch_raw,
        "patch_recounted": patch_recounted,
        "oracle_files": files,
        "fail_to_pass": task.get("FAIL_TO_PASS", []) or [],
        "pass_to_pass": task.get("PASS_TO_PASS", []) or [],
        "gpu_inference": model_out.get("gpu", _empty_gpu_stats()),
        "gpu_harness": gpu_harness_stats,
        **result_payload,
    }

    out_file = out_dir / f"{instance_id}.json"
    out_file.write_text(json.dumps(task_record, indent=2))
    # One-line per-task summary. Progress + ETA computed by caller from records list.
    gpu_inf = task_record["gpu_inference"]
    gpu_hint = (
        f" vram_max={gpu_inf['vram_max_mib']}MiB tempC_max={gpu_inf['gpu_temp_max_c']} util_max={gpu_inf['gpu_util_max_pct']}%"
        if gpu_inf.get("samples", 0) > 0
        else ""
    )
    trunc = " TRUNCATED_BY_LENGTH" if model_out.get("truncated_by_length") else ""
    print(
        f"  [{task_idx}/{task_total}] ok  wall={model_out['wall_seconds']}s "
        f"toks={model_out['completion_tokens']}/{model_out.get('max_tokens_requested', '?')} "
        f"resolved={result_payload.get('resolved')}"
        f"{gpu_hint}{trunc}",
        flush=True,
    )
    return task_record


# ---------- entrypoint ----------


def _emit_summary(out_dir: Path, records: list[dict], total_wall: float) -> None:
    """Compute + write summary.json. Extracted so KeyboardInterrupt path can call it too."""
    resolved = [r for r in records if r.get("resolved") is True]
    unresolved = [r for r in records if r.get("resolved") is False]
    unknown = [r for r in records if r.get("resolved") is None]
    errors = [r for r in records if "error" in r]
    ctx_skipped = [r for r in records if r.get("context_budget_skipped")]
    length_truncated = [r for r in records if r.get("truncated_by_length")]
    walls = [r["wall_seconds"] for r in records if isinstance(r.get("wall_seconds"), (int, float))]
    # GPU aggregates across all tasks (inference window only; harness window is
    # usually idle and would drown out the signal).
    gpu_valid = [r.get("gpu_inference", {}) for r in records
                 if r.get("gpu_inference", {}).get("samples", 0) > 0]
    gpu_summary = None
    if gpu_valid:
        gpu_summary = {
            "tasks_with_gpu_samples": len(gpu_valid),
            "vram_max_mib_across_tasks": max(g["vram_max_mib"] for g in gpu_valid),
            "vram_avg_mib_across_tasks": round(statistics.fmean(g["vram_avg_mib"] for g in gpu_valid), 1),
            "gpu_temp_max_c_across_tasks": max(g["gpu_temp_max_c"] for g in gpu_valid),
            "gpu_temp_avg_c_across_tasks": round(statistics.fmean(g["gpu_temp_avg_c"] for g in gpu_valid), 2),
            "power_max_w_across_tasks": round(max(g["power_max_w"] for g in gpu_valid), 2),
            "power_avg_w_across_tasks": round(statistics.fmean(g["power_avg_w"] for g in gpu_valid), 2),
            "gpu_util_max_pct_across_tasks": max(g["gpu_util_max_pct"] for g in gpu_valid),
            "gpu_util_avg_pct_across_tasks": round(statistics.fmean(g["gpu_util_avg_pct"] for g in gpu_valid), 2),
        }
    summary = {
        "task_count": len(records),
        "resolved_true": len(resolved),
        "resolved_false": len(unresolved),
        "resolved_unknown_or_stubbed": len(unknown),
        "errors": len(errors),
        "context_budget_skipped": len(ctx_skipped),
        "truncated_by_length": len(length_truncated),
        "pass_at_1": (len(resolved) / len(records)) if records else 0.0,
        "wall_total_s": round(total_wall, 2),
        "wall_total_hms": _fmt_dur(total_wall),
        "wall_median_per_task_s": round(statistics.median(walls), 2) if walls else 0.0,
        "wall_mean_per_task_s": round(statistics.mean(walls), 2) if walls else 0.0,
        "estimated_full_500_wall_hours": round((statistics.mean(walls) * 500 / 3600), 2) if walls else 0.0,
        "gpu": gpu_summary,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("[F.3 Path A] done. summary:", json.dumps(summary, indent=2), sep="\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    task_group = ap.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--tasks", help="instance_id, comma-separated list, or 'all'")
    task_group.add_argument("--smoke", "--smoke-25", dest="smoke_25",
                            action="store_true",
                            help="calibrated 30-task smoke stratified from F.3 "
                                 "full-500 ground truth (predicts full-500 pass@1 "
                                 "within ~3pt). --smoke-25 kept as alias for "
                                 "backward compat, but now runs the 30-task set.")
    ap.add_argument("--model", choices=list(CELLS.keys()), default="c01",
                    help="model cell to test (default: c01, the ratified coder)")
    ap.add_argument("--dry-plan-only", action="store_true",
                    help="skip docker apply_and_test; exercise everything else")
    ap.add_argument("--keep-sandbox", action="store_true",
                    help="don't rm sandbox container after test run (debug)")
    ap.add_argument("--resume-run", metavar="DIR",
                    help="resume into an existing run dir; skip tasks whose "
                         "<instance_id>.json already contains a completed record")
    args = ap.parse_args(argv)

    # Resolve task list.
    if args.smoke_25:
        ids = list(SMOKE_TASK_IDS)
    elif args.tasks == "all":
        ids = ["all"]
    else:
        ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
    tasks = load_tasks(ids)
    print(f"[F.3 Path A] resolved {len(tasks)} task(s); model={args.model}; "
          f"dry_plan_only={args.dry_plan_only}", flush=True)

    # Prepare output dir (new or resumed).
    if args.resume_run:
        out_dir = Path(args.resume_run).expanduser().resolve()
        if not out_dir.is_dir():
            print(f"[F.3 Path A] --resume-run dir does not exist: {out_dir}", flush=True)
            return 2
        ts = out_dir.name.split("_run")[0] if out_dir.name.endswith("_run") else datetime.now().strftime("%Y%m%d_%H%M")
        print(f"[F.3 Path A] resuming into {out_dir}", flush=True)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_dir = BENCH_ROOT / f"{ts}_run"
        out_dir.mkdir(parents=True, exist_ok=True)

    # Manifest (append a new one on resume; original preserved as manifest.json).
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
        "smoke": bool(args.smoke_25),
        "smoke_task_count": len(SMOKE_TASK_IDS) if args.smoke_25 else 0,
        "resumed": bool(args.resume_run),
    }
    try:
        manifest["git_sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        manifest["git_sha"] = "unknown"
    manifest_path = out_dir / ("manifest.json" if not (out_dir / "manifest.json").exists()
                               else f"manifest_resume_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Resumption: preload existing per-task records so summary reflects total
    # progress. Skip re-running tasks whose JSON already contains a completed
    # record (not a `phase: harness_error` and not an empty file).
    records: list[dict] = []
    already_done: set[str] = set()
    if args.resume_run:
        for existing in sorted(out_dir.glob("*.json")):
            if existing.name in ("summary.json", "manifest.json") or existing.name.startswith("manifest_"):
                continue
            try:
                r = json.loads(existing.read_text())
            except json.JSONDecodeError:
                continue
            inst = r.get("instance_id")
            # Consider a task "done" if it has a completion phase we don't want to redo.
            phase = r.get("phase")
            has_resolution = r.get("resolved") in (True, False)
            if inst and (has_resolution or phase == "dry-plan-only-skipped-docker"):
                records.append(r)
                already_done.add(inst)
        print(f"[F.3 Path A] resume: {len(already_done)} tasks already complete; "
              f"skipping those", flush=True)

    remaining = [t for t in tasks if t["instance_id"] not in already_done]
    if args.resume_run:
        print(f"[F.3 Path A] {len(remaining)} tasks remain to run", flush=True)

    # Numbering. task_total = full run size (already-done + remaining).
    # task_idx counts within the FULL sequence so resumed runs pick up at the
    # right number, matching what a fresh log would show.
    task_total = len(already_done) + len(remaining)
    start_idx = len(already_done) + 1  # 1-based

    def _write_progress(session_elapsed: float, completed_this_session: int) -> None:
        """Live-tailable progress file. Written after every task + at end."""
        resolved = sum(1 for r in records if r.get("resolved") is True)
        unresolved = sum(1 for r in records if r.get("resolved") is False)
        completed = len(records)
        remaining_count = task_total - completed
        eta_s = 0.0
        if completed_this_session > 0 and remaining_count > 0:
            per_task = session_elapsed / completed_this_session
            eta_s = per_task * remaining_count
        (out_dir / "progress.json").write_text(json.dumps({
            "task_total": task_total,
            "completed": completed,
            "remaining": remaining_count,
            "resolved_true": resolved,
            "resolved_false": unresolved,
            "pass_at_1_so_far": round((resolved / completed), 4) if completed else 0.0,
            "session_elapsed_s": round(session_elapsed, 2),
            "session_elapsed_hms": _fmt_dur(session_elapsed),
            "eta_remaining_s": round(eta_s, 2),
            "eta_remaining_hms": _fmt_dur(eta_s),
            "completed_this_session": completed_this_session,
        }, indent=2))

    # Run.
    t0 = time.time()
    for i, task in enumerate(remaining):
        task_idx = start_idx + i
        try:
            rec = run_task(task, args.model, out_dir, args.dry_plan_only, args.keep_sandbox,
                           task_idx=task_idx, task_total=task_total)
            records.append(rec)
            session_elapsed = time.time() - t0
            done_this_session = i + 1
            _write_progress(session_elapsed, done_this_session)
            resolved_so_far = sum(1 for r in records if r.get("resolved") is True)
            per_task = session_elapsed / done_this_session if done_this_session else 0.0
            eta_s = per_task * (task_total - len(records))
            print(
                f"  progress: {len(records)}/{task_total} "
                f"resolved={resolved_so_far}/{len(records)} "
                f"elapsed={_fmt_dur(session_elapsed)} "
                f"eta={_fmt_dur(eta_s)}",
                flush=True,
            )
        except KeyboardInterrupt:
            print("[F.3 Path A] interrupted; partial results in", out_dir, flush=True)
            _write_progress(time.time() - t0, i)
            _emit_summary(out_dir, records, time.time() - t0)
            return 130
        except Exception as e:
            print(f"[F.3 Path A] task {task['instance_id']} failed: {type(e).__name__}: {e}", flush=True)
            records.append({"instance_id": task["instance_id"], "task_index": task_idx,
                            "task_total": task_total, "phase": "harness_error",
                            "error": f"{type(e).__name__}: {e}"})
            _write_progress(time.time() - t0, i + 1)

    total_wall = time.time() - t0
    _write_progress(total_wall, len(remaining))
    _emit_summary(out_dir, records, total_wall)
    print("[F.3 Path A] artifacts:", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
