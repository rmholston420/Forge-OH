#!/usr/bin/env python3
"""Path F bench — Path E harness + NVML instrumentation.

Extends Path E with per-request GPU sampling (util/vram/temp/power) via
pynvml at 500ms cadence. Same warmup + 3 scored runs per (cell, prompt).

Aggregation:
    - Latency stats: min/med/max across 3 scored runs (unchanged from Path E)
    - GPU stats aggregated across ALL scored runs of the same (cell, prompt):
        gpu_util: avg-of-avg, max-of-max
        vram:     avg-of-avg, max-of-max
        temp:     avg-of-avg, max-of-max
        power:    avg-of-avg, max-of-max
    - Per-run gpu snapshots also preserved in `runs_gpu` for auditability.

Cells: same as Path E CELLS. Path F does NOT redefine cells — it re-benches
the ADR-013 shortlist (c11, c03b, c01) plus arbitrary cells specified on
the CLI.

Output: ~/.forge-oh/bench_pathF/<TS>_run/{cell_id}__{prompt_name}.json

ADR-013 amendment #2 lands after Path F Tier 1 (LiveCodeBench) → Tier 2
(SWE-bench Verified) evaluate the top-3 coder candidates on
external-standard benchmarks (in a separate runner).
"""
import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import request as urlreq, error as urlerr

# Path F lives alongside Path E — reuse the same prompts dir + gold dir.
REPO = Path.home() / "dev" / "forge-oh"
PROMPTS_DIR = REPO / "bench" / "prompts"
PROMPTS = ["debug", "arch", "plan"]

# NVML sampler — sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nvml_sampler import GpuSampler  # noqa: E402

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# Cells: (cell_id, role, runtime, endpoint, model_id_at_endpoint, sampling_profile)
# Copied verbatim from bench_pathE.py so Path F can rebench any cell. Path F
# adds no new cells — it re-benches with instrumentation.
CELLS = {
    "c01": ("coder",   "vllm",   "http://localhost:8000/v1",  "c01_coder_vllm_qwen36_27b_int4",     "coder_nothink"),
    "c02": ("coder",   "vllm",   "http://localhost:8000/v1",  "c02_coder_vllm_qwen36_35b_nvfp4",    "coder_nothink"),
    "c03": ("coder",   "ollama", "http://localhost:11434/v1", "qwen3-coder:latest",                 "coder"),
    "c03b":("coder",   "vllm",   "http://localhost:8000/v1",  "c03b_coder_vllm_qwen3coder_awq",     "coder_nothink"),
    "c04": ("planner", "vllm",   "http://localhost:8000/v1",  "c04_planner_vllm_qwen36_27b_nvfp4",  "thinking"),
    "c05": ("planner", "vllm",   "http://localhost:8000/v1",  "c05_planner_vllm_qwen3thinking_awq", "thinking"),
    "c08": ("coder",   "ollama", "http://localhost:11434/v1", "yi:34b-chat-v1.5-q4_K_M",            "coder"),
    "c09": ("coder",   "vllm",   "http://localhost:8000/v1",  "c09_coder_vllm_codestral22b_awq",    "coder_nothink"),
    "c11": ("coder",   "vllm",   "http://localhost:8000/v1",  "c11_coder_vllm_devstral24b_awq",     "coder_nothink_mistral"),
    "c12a":("coder",   "vllm",   "http://localhost:8000/v1",  "c12a_coder_vllm_dsr1_distill32b_awq",  "coder_nothink"),
    "c12b":("planner", "vllm",   "http://localhost:8000/v1",  "c12b_planner_vllm_dsr1_distill32b_awq", "thinking"),
}

# Recommended shortlist for ADR-013 coder rebench:
#   c11, c03b, c01 — top-3 by aggregated Council score, all universally
#   arch-gated → Path F tests instrumented rebench, then LiveCodeBench.
DEFAULT_SHORTLIST = ["c11", "c03b", "c01"]

SAMPLING = {
    "coder": {
        "temperature": 0.7, "top_p": 0.8, "top_k": 20,
        "min_p": 0.0, "presence_penalty": 1.0,
        "max_tokens": 4096,
    },
    "coder_nothink": {
        "temperature": 0.7, "top_p": 0.8, "top_k": 20,
        "min_p": 0.0, "presence_penalty": 1.0,
        "max_tokens": 4096,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    "coder_nothink_mistral": {
        "temperature": 0.7, "top_p": 0.8, "top_k": 20,
        "min_p": 0.0, "presence_penalty": 1.0,
        "max_tokens": 4096,
    },
    "thinking": {
        "temperature": 0.6, "top_p": 0.95, "top_k": 20,
        "min_p": 0.0, "presence_penalty": 1.0,
        "max_tokens": 8192,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
    },
}


def load_prompts():
    return {name: (PROMPTS_DIR / f"{name}.txt").read_text() for name in PROMPTS}


def post_chat(endpoint, model, prompt_text, sampling, timeout=900):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "stream": False,
    }
    sampling = dict(sampling)
    extra = sampling.pop("extra_body", None)
    payload.update(sampling)
    if extra:
        payload.update(extra)
    body = json.dumps(payload).encode("utf-8")
    req = urlreq.Request(
        f"{endpoint}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urlreq.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urlerr.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:2000]}", "latency_s": time.time() - t0}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "latency_s": time.time() - t0}
    latency = time.time() - t0
    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    usage = data.get("usage", {}) or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    return {
        "latency_s": latency,
        "content": content,
        "reasoning_content": reasoning,
        "usage": usage,
        "finish_reason": choice.get("finish_reason"),
    }


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()


def _post_chat_with_gpu(endpoint, model, prompt_text, sampling, sample_interval_s):
    """Wrap post_chat with a GPU sampler around the request."""
    sampler = GpuSampler(interval_s=sample_interval_s)
    sampler.start()
    try:
        out = post_chat(endpoint, model, prompt_text, sampling)
    finally:
        gpu = sampler.stop()
    out["gpu"] = gpu.to_dict()
    return out


def _aggregate_gpu_across_runs(runs_gpu):
    """Aggregate per-run GpuStats.to_dict() into cross-run avg/max.

    avg-of-avg for the *_avg_* fields; max-of-max for the *_max_* fields.
    """
    if not runs_gpu:
        return None
    # Only aggregate runs that actually had NVML samples.
    valid = [g for g in runs_gpu if g.get("samples", 0) > 0]
    if not valid:
        return {"samples_total": 0, "nvml_available": False, "runs": len(runs_gpu)}
    return {
        "runs": len(runs_gpu),
        "runs_with_samples": len(valid),
        "samples_total": sum(g["samples"] for g in valid),
        "nvml_available": True,
        "gpu_util_avg_pct": round(statistics.fmean(g["gpu_util_avg_pct"] for g in valid), 2),
        "gpu_util_max_pct": max(g["gpu_util_max_pct"] for g in valid),
        "vram_avg_mib": round(statistics.fmean(g["vram_avg_mib"] for g in valid), 1),
        "vram_max_mib": max(g["vram_max_mib"] for g in valid),
        "gpu_temp_avg_c": round(statistics.fmean(g["gpu_temp_avg_c"] for g in valid), 2),
        "gpu_temp_max_c": max(g["gpu_temp_max_c"] for g in valid),
        "power_avg_w": round(statistics.fmean(g["power_avg_w"] for g in valid), 2),
        "power_max_w": round(max(g["power_max_w"] for g in valid), 2),
    }


def run_cell(cell_id, prompts_dict, runs=3, warmup=True, sample_interval_s=0.5):
    role, runtime, endpoint, model, profile = CELLS[cell_id]
    cell_t0 = time.time()
    print(f"\n=== [{_ts()}] {cell_id} ({role}/{runtime}/{model}) ===", flush=True)
    results = {}
    for prompt_name, prompt_text in prompts_dict.items():
        prompt_t0 = time.time()
        print(f"  [{_ts()}] [{prompt_name}] ", end="", flush=True)
        latencies = []
        runs_gpu = []
        final_out = None
        if warmup:
            print("warmup ", end="", flush=True)
            _ = _post_chat_with_gpu(endpoint, model, prompt_text, SAMPLING[profile], sample_interval_s)
        for i in range(runs):
            print(f"r{i+1} ", end="", flush=True)
            out = _post_chat_with_gpu(endpoint, model, prompt_text, SAMPLING[profile], sample_interval_s)
            if "error" in out:
                print(f"ERR: {out['error'][:100]}", flush=True)
                results[prompt_name] = {
                    "cell": cell_id, "role": role, "runtime": runtime,
                    "model": model, "profile": profile,
                    "error": out["error"],
                    "latency_s": out.get("latency_s"),
                    "gpu": out.get("gpu"),
                }
                final_out = None
                break
            latencies.append(out["latency_s"])
            runs_gpu.append(out["gpu"])
            final_out = out
        prompt_wall = time.time() - prompt_t0
        if final_out is not None:
            usage = final_out["usage"]
            comp_tokens = usage.get("completion_tokens", 0)
            tok_per_s = (comp_tokens / statistics.median(latencies)) if latencies and comp_tokens else 0.0
            raw = final_out["content"]
            stripped = THINK_RE.sub("", raw).strip()
            gpu_agg = _aggregate_gpu_across_runs(runs_gpu)
            results[prompt_name] = {
                "cell": cell_id, "role": role, "runtime": runtime,
                "model": model, "profile": profile,
                "runs": len(latencies),
                "warmup": warmup,
                "latency_min_s": min(latencies),
                "latency_med_s": statistics.median(latencies),
                "latency_max_s": max(latencies),
                "completion_tokens": comp_tokens,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "tokens_per_s_med": round(tok_per_s, 2),
                "finish_reason": final_out["finish_reason"],
                "content_raw": raw,
                "content_stripped": stripped,
                "prompt_wall_s": round(prompt_wall, 2),
                "content_raw_chars": len(raw),
                "content_stripped_chars": len(stripped),
                "reasoning_content": final_out["reasoning_content"],
                "gpu_aggregate": gpu_agg,
                "runs_gpu": runs_gpu,
                "sample_interval_s": sample_interval_s,
            }
            g = gpu_agg or {}
            print(
                f"OK {statistics.median(latencies):.1f}s med, {comp_tokens}tok, {tok_per_s:.1f}tok/s "
                f"| VRAM avg={g.get('vram_avg_mib', 0):.0f}MiB max={g.get('vram_max_mib', 0)}MiB "
                f"| util avg={g.get('gpu_util_avg_pct', 0):.0f}% max={g.get('gpu_util_max_pct', 0)}% "
                f"| temp avg={g.get('gpu_temp_avg_c', 0):.0f}C max={g.get('gpu_temp_max_c', 0)}C "
                f"| pwr avg={g.get('power_avg_w', 0):.0f}W max={g.get('power_max_w', 0):.0f}W",
                flush=True,
            )
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="+", default=None,
                    help=f"cell ids or 'shortlist' or 'all'. valid: {list(CELLS)}. "
                         f"default: {DEFAULT_SHORTLIST}")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--sample-interval", type=float, default=0.5,
                    help="NVML sampling interval in seconds (default 0.5)")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--smoke", action="store_true",
                    help="Smoke test: run 1 prompt (debug) x 1 run on 1 cell to verify instrumentation.")
    args = ap.parse_args()

    if args.cells is None or args.cells == ["shortlist"]:
        cells = DEFAULT_SHORTLIST
    elif args.cells == ["all"]:
        cells = list(CELLS)
    else:
        cells = args.cells

    for c in cells:
        if c not in CELLS:
            print(f"unknown cell {c}. valid: {list(CELLS)}", file=sys.stderr)
            sys.exit(2)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path.home() / ".forge-oh" / "bench_pathF" / f"{ts}_run"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"OUT: {out_dir}", flush=True)
    print(f"CELLS: {cells}", flush=True)
    print(f"RUNS: {args.runs} scored{' + warmup' if not args.no_warmup else ' (no warmup)'}", flush=True)
    print(f"SAMPLE_INTERVAL: {args.sample_interval}s", flush=True)

    prompts_dict = load_prompts()
    if args.smoke:
        # Restrict to a single fast prompt for smoke test.
        prompts_dict = {"debug": prompts_dict["debug"]}
        args.runs = 1
        print("SMOKE MODE: 1 prompt (debug) x 1 run, no warmup", flush=True)
        args.no_warmup = True

    all_results = {}
    overall_t0 = time.time()
    for cell_id in cells:
        cell_start = time.time()
        per_prompt = run_cell(
            cell_id, prompts_dict,
            runs=args.runs,
            warmup=not args.no_warmup,
            sample_interval_s=args.sample_interval,
        )
        print(f"  [{_ts()}] cell {cell_id} done in {time.time() - cell_start:.1f}s", flush=True)
        for prompt_name, result in per_prompt.items():
            fp = out_dir / f"{cell_id}__{prompt_name}.json"
            fp.write_text(json.dumps(result, indent=2))
            all_results[f"{cell_id}__{prompt_name}"] = result

    print(f"\n[{_ts()}] ALL CELLS DONE in {time.time() - overall_t0:.1f}s", flush=True)
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "ts": ts,
        "cells_ran": cells,
        "runs": args.runs,
        "warmup": not args.no_warmup,
        "sample_interval_s": args.sample_interval,
        "smoke": args.smoke,
        "total_wall_s": round(time.time() - overall_t0, 2),
        "results_index": sorted(all_results.keys()),
        "cells_definition": {k: {"role": v[0], "runtime": v[1], "endpoint": v[2], "model": v[3], "profile": v[4]}
                             for k, v in CELLS.items() if k in cells},
    }, indent=2))
    print(f"\nDONE. {len(all_results)} results in {out_dir}", flush=True)


if __name__ == "__main__":
    main()
