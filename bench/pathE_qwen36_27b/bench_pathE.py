#!/usr/bin/env python3
"""Path E bench — Qwen3.6-27B (proposed new coder + planner) vs ADR-009 baseline.

Cells (5 total, quality-first scoring):
    c01_coder_vllm_qwen36_27b_int4      — PROPOSED coder pick
    c02_coder_vllm_qwen36_35b_nvfp4     — ADR-009 baseline (coder)
    c03_coder_ollama_qwen3coder_32k     — current Ollama fallback (floor)
    c04_planner_vllm_qwen36_27b_nvfp4   — PROPOSED planner pick
    c05_planner_vllm_qwen3thinking_awq  — ADR-009 baseline (planner)

Bench methodology: quality-first, speed-second tiebreak within 3 points.
Ties within 3 quality points → higher tok/s wins. Never declare a winner
on speed alone. Prompts on disk. One JSON per cell x prompt. Strip
<think> before dumping for gold-standard scoring.

Ollama cells first, then vLLM cells grouped by model, to minimize container
restart overhead (see forge-oh-bench-methodology skill § Bench Ordering Rule).

Output: ~/.forge-oh/bench_pathE/<TS>_run/{cell_id}__{prompt_name}.json
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

REPO = Path.home() / "dev" / "forge-oh"
PROMPTS_DIR = REPO / "bench" / "prompts"
PROMPTS = ["debug", "arch", "plan"]

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# Cells: (cell_id, role, runtime, endpoint, model_id_at_endpoint, sampling_profile)
CELLS = {
    # coder-role cells
    "c01": ("coder",   "vllm",   "http://localhost:8000/v1",  "c01_coder_vllm_qwen36_27b_int4",     "coder_nothink"),
    "c02": ("coder",   "vllm",   "http://localhost:8000/v1",  "c02_coder_vllm_qwen36_35b_nvfp4",    "coder_nothink"),
    "c03": ("coder",   "ollama", "http://localhost:11434/v1", "qwen3-coder:latest",                 "coder"),
    "c03b":("coder",   "vllm",   "http://localhost:8000/v1",  "c03b_coder_vllm_qwen3coder_awq",     "coder_nothink"),
    # planner-role cells
    "c04": ("planner", "vllm",   "http://localhost:8000/v1",  "c04_planner_vllm_qwen36_27b_nvfp4",  "thinking"),
    "c05": ("planner", "vllm",   "http://localhost:8000/v1",  "c05_planner_vllm_qwen3thinking_awq", "thinking"),
    # F.19-post expansion — broader coder/planner matrix.
    "c08": ("coder",   "ollama", "http://localhost:11434/v1", "yi:34b-chat-v1.5-q4_K_M",              "coder"),
    "c09": ("coder",   "vllm",   "http://localhost:8000/v1",  "c09_coder_vllm_codestral22b_awq",    "coder_nothink"),
    # c10 (Devstral NVFP4) dropped 2026-08-05 01:27 EDT — Fireworks repo has no
    # params.json/consolidated.safetensors; MistralCommonBackend hijacks the
    # tokenizer factory and get_chat_template fails. c11 covers Devstral alone.
    "c11": ("coder",   "vllm",   "http://localhost:8000/v1",  "c11_coder_vllm_devstral24b_awq",     "coder_nothink_mistral"),
    # DeepSeek-R1 distill — same weights benched under two roles.
    "c12a":("coder",   "vllm",   "http://localhost:8000/v1",  "c12a_coder_vllm_dsr1_distill32b_awq", "coder_nothink"),
    "c12b":("planner", "vllm",   "http://localhost:8000/v1",  "c12b_planner_vllm_dsr1_distill32b_awq", "thinking"),
}

# Ordering rule (Ollama first, then vLLM grouped by model):
# Full-matrix ordering (Ollama first — hot-swap free; vLLM grouped by model to minimize restarts):
#   c03  → c08         (Ollama)
#   c01 → c02 → c02-rerun → c04 → c05 → c03b → c09 → c11 → c12a → c12b   (vLLM)
# (c01/c02/c04/c05 are separate vLLM launches; c01 & c04 share weights but
#  differ in --reasoning-parser / --enable-reasoning flags so they run in
#  separate containers).
CELL_ORDER = [
    # Ollama first (hot-swap, no container restart cost)
    "c03", "c08",
    # vLLM — grouped by model to minimize container reloads
    "c01", "c02", "c04", "c05",
    "c03b",
    "c09",
    "c11",
    "c12a", "c12b",
]

SAMPLING = {
    "coder": {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.0,
        "max_tokens": 4096,
        # Ollama-only: cap KV cache at 32K instead of the model's declared 262K.
        # Full 262K KV would exceed 32 GB VRAM and force CPU-offload (~1 tok/s).
        "extra_body": {"options": {"num_ctx": 32768, "num_predict": 4096}},
    },
    "coder_nothink": {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.0,
        "max_tokens": 4096,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    # coder_nothink_mistral: identical sampling to coder_nothink, but without
    # chat_template_kwargs. MistralCommonBackend rejects any request that
    # carries chat_template or chat_template_kwargs fields with
    # HTTP 400: "chat_template is not supported for Mistral tokenizers".
    # Mistral tokenizer models have no thinking mode anyway, so the flag is
    # a no-op even where accepted. Use for cells that launch with
    # --tokenizer-mode mistral (c11 Devstral AWQ).
    "coder_nothink_mistral": {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.0,
        "max_tokens": 4096,
    },
    "thinking": {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.0,
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
    sampling = dict(sampling)  # defensive copy
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


def run_cell(cell_id, prompts_dict, runs=3, warmup=True):
    role, runtime, endpoint, model, profile = CELLS[cell_id]
    cell_t0 = time.time()
    print(f"\n=== [{_ts()}] {cell_id} ({role}/{runtime}/{model}) ===", flush=True)
    results = {}
    for prompt_name, prompt_text in prompts_dict.items():
        prompt_t0 = time.time()
        print(f"  [{_ts()}] [{prompt_name}] ", end="", flush=True)
        latencies = []
        final_out = None
        if warmup:
            print("warmup ", end="", flush=True)
            _ = post_chat(endpoint, model, prompt_text, SAMPLING[profile])
        for i in range(runs):
            print(f"r{i+1} ", end="", flush=True)
            out = post_chat(endpoint, model, prompt_text, SAMPLING[profile])
            if "error" in out:
                print(f"ERR: {out['error'][:100]}", flush=True)
                results[prompt_name] = {
                    "cell": cell_id, "role": role, "runtime": runtime,
                    "model": model, "profile": profile,
                    "error": out["error"],
                    "latency_s": out.get("latency_s"),
                }
                final_out = None
                break
            latencies.append(out["latency_s"])
            final_out = out
        prompt_wall = time.time() - prompt_t0
        if final_out is not None:
            usage = final_out["usage"]
            comp_tokens = usage.get("completion_tokens", 0)
            tok_per_s = (comp_tokens / statistics.median(latencies)) if latencies and comp_tokens else 0.0
            raw = final_out["content"]
            stripped = THINK_RE.sub("", raw).strip()
            results[prompt_name] = {
                "cell": cell_id, "role": role, "runtime": runtime,
                "model": model, "profile": profile,
                "runs": len(latencies),
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
            }
            print(f"OK {statistics.median(latencies):.1f}s med, {comp_tokens}tok, {tok_per_s:.1f}tok/s", flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="+", required=True,
                    help=f"cell ids or 'all'. valid: {list(CELLS)}. Recommended order: {CELL_ORDER}")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    if args.cells == ["all"]:
        args.cells = CELL_ORDER

    for c in args.cells:
        if c not in CELLS:
            print(f"unknown cell {c}. valid: {list(CELLS)}", file=sys.stderr)
            sys.exit(2)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path.home() / ".forge-oh" / "bench_pathE" / f"{ts}_run"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"OUT: {out_dir}", flush=True)

    prompts_dict = load_prompts()
    all_results = {}
    overall_t0 = time.time()
    for cell_id in args.cells:
        cell_start = time.time()
        per_prompt = run_cell(cell_id, prompts_dict, runs=args.runs, warmup=not args.no_warmup)
        print(f"  [{_ts()}] cell {cell_id} done in {time.time() - cell_start:.1f}s", flush=True)
        for prompt_name, result in per_prompt.items():
            fp = out_dir / f"{cell_id}__{prompt_name}.json"
            fp.write_text(json.dumps(result, indent=2))
            all_results[f"{cell_id}__{prompt_name}"] = result

    print(f"\n[{_ts()}] ALL CELLS DONE in {time.time() - overall_t0:.1f}s", flush=True)
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "ts": ts,
        "cells_ran": args.cells,
        "runs": args.runs,
        "total_wall_s": round(time.time() - overall_t0, 2),
        "results_index": sorted(all_results.keys()),
        "cells_definition": {k: {"role": v[0], "runtime": v[1], "endpoint": v[2], "model": v[3], "profile": v[4]}
                             for k, v in CELLS.items()},
    }, indent=2))
    print(f"\nDONE. {len(all_results)} results in {out_dir}", flush=True)


if __name__ == "__main__":
    main()
