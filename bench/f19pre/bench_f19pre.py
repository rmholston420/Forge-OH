#!/usr/bin/env python3
"""F.19-pre bench harness. 8 cells x 3 prompts. Ollama + vLLM.
Runs one cell at a time against whichever endpoint is live.
Output: ~/.forge-oh/bench_f19pre/<TS>_run/{cell_id}__{prompt_name}.json
"""
import argparse, json, os, statistics, sys, time
from datetime import datetime
from pathlib import Path
from urllib import request as urlreq, error as urlerr

REPO = Path.home() / "dev" / "forge-oh"
PROMPTS_DIR = REPO / "bench" / "prompts"
PROMPTS = ["debug", "arch", "plan"]

# Cells: (cell_id, role, runtime, endpoint, model_id_at_endpoint, sampling_profile)
CELLS = {
    "c01": ("coder",   "ollama", "http://localhost:11434/v1", "qwen3-coder:30b",                  "coder"),
    "c02": ("coder",   "vllm",   "http://localhost:8000/v1",  "c02_coder_vllm_qwen3coder_awq",    "coder"),
    "c03": ("coder",   "ollama", "http://localhost:11434/v1", "qwen3.6:35b-a3b",                  "coder_nothink"),
    "c04": ("coder",   "vllm",   "http://localhost:8000/v1",  "c04_coder_vllm_qwen36_nvfp4",      "coder_nothink"),
    "c05": ("planner", "ollama", "http://localhost:11434/v1", "qwen3.6:35b-a3b",                  "thinking"),
    "c06": ("planner", "vllm",   "http://localhost:8000/v1",  "c06_planner_vllm_qwen36_nvfp4",    "thinking"),
    "c07": ("planner", "ollama", "http://localhost:11434/v1", "qwen3-thinking-2507:q4kxl",        "thinking"),
    "c08": ("planner", "vllm",   "http://localhost:8000/v1",  "c08_planner_vllm_thinking_awq",    "thinking"),
}

SAMPLING = {
    "coder":         {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.0, "max_tokens": 2048},
    "coder_nothink": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.0, "max_tokens": 2048, "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    "thinking":      {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 4096, "extra_body": {"chat_template_kwargs": {"enable_thinking": True}}},
}

def load_prompts():
    return {name: (PROMPTS_DIR / f"{name}.txt").read_text() for name in PROMPTS}

def post_chat(endpoint, model, prompt_text, sampling, timeout=600):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "stream": False,
    }
    extra = sampling.pop("extra_body", None) if "extra_body" in sampling else None
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

def run_cell(cell_id, prompts_dict, runs=3, warmup=True):
    role, runtime, endpoint, model, profile = CELLS[cell_id]
    print(f"\n=== {cell_id} ({role}/{runtime}/{model}) ===", flush=True)
    results = {}
    for prompt_name, prompt_text in prompts_dict.items():
        print(f"  [{prompt_name}] ", end="", flush=True)
        latencies = []
        final_out = None
        if warmup:
            print("warmup ", end="", flush=True)
            _ = post_chat(endpoint, model, prompt_text, dict(SAMPLING[profile]))
        for i in range(runs):
            print(f"r{i+1} ", end="", flush=True)
            out = post_chat(endpoint, model, prompt_text, dict(SAMPLING[profile]))
            if "error" in out:
                print(f"ERR: {out['error'][:100]}", flush=True)
                results[prompt_name] = {"cell": cell_id, "role": role, "runtime": runtime, "model": model, "profile": profile, "error": out["error"], "latency_s": out.get("latency_s")}
                final_out = None
                break
            latencies.append(out["latency_s"])
            final_out = out
        if final_out is not None:
            usage = final_out["usage"]
            comp_tokens = usage.get("completion_tokens", 0)
            tok_per_s = (comp_tokens / statistics.median(latencies)) if latencies and comp_tokens else 0.0
            results[prompt_name] = {
                "cell": cell_id, "role": role, "runtime": runtime, "model": model, "profile": profile,
                "runs": len(latencies),
                "latency_min_s": min(latencies), "latency_med_s": statistics.median(latencies), "latency_max_s": max(latencies),
                "completion_tokens": comp_tokens, "prompt_tokens": usage.get("prompt_tokens", 0),
                "tokens_per_s_med": round(tok_per_s, 2),
                "finish_reason": final_out["finish_reason"],
                "content": final_out["content"],
                "reasoning_content": final_out["reasoning_content"],
            }
            print(f"OK {statistics.median(latencies):.1f}s med, {comp_tokens}tok, {tok_per_s:.1f}tok/s", flush=True)
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="+", required=True, help="cell ids to run e.g. c01 c02")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    for c in args.cells:
        if c not in CELLS:
            print(f"unknown cell {c}. valid: {list(CELLS)}", file=sys.stderr)
            sys.exit(2)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path.home() / ".forge-oh" / "bench_f19pre" / f"{ts}_run"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"OUT: {out_dir}", flush=True)

    prompts_dict = load_prompts()
    all_results = {}
    for cell_id in args.cells:
        per_prompt = run_cell(cell_id, prompts_dict, runs=args.runs, warmup=not args.no_warmup)
        for prompt_name, result in per_prompt.items():
            fp = out_dir / f"{cell_id}__{prompt_name}.json"
            fp.write_text(json.dumps(result, indent=2))
            all_results[f"{cell_id}__{prompt_name}"] = result

    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({"ts": ts, "cells": args.cells, "runs": args.runs, "results_index": sorted(all_results.keys())}, indent=2))
    print(f"\nDONE. {len(all_results)} results in {out_dir}", flush=True)

if __name__ == "__main__":
    main()
