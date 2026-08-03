#!/usr/bin/env python3
"""F.19.4 Phase 1 — direct LLM completion probe through route_by_role.

Reads bench/prompts/{arch,debug,plan}.txt, resolves each via the
router's role map, calls the resolved backend's OpenAI-compat
/chat/completions endpoint, and prints:

  - Prompt name + taskComplexity → role mapping
  - Resolved backend, model, base_url, max_tokens
  - Cold-start time (first token latency proxy: full response time)
  - Completion length (chars, non-empty check)
  - Any error

Runs from within the bff/ venv (LiteLLM/httpx available).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# --- Set env BEFORE importing router to make sure defaults resolve ---
# The router already reads env at import; don't set anything special —
# rely on the same defaults the BFF would see.
from bff.routers.runs import _TASK_COMPLEXITY_TO_ROLE  # noqa: E402
from bff.services.model_router import (  # noqa: E402
    ModelUnavailableError,
    route_by_role,
)

# ADR-009 canonical prompt tiers.
PROMPTS = [
    # (name, taskComplexity, path)
    ("P1", "simple", REPO_ROOT / "bench" / "prompts" / "arch.txt"),
    ("P2", "medium", REPO_ROOT / "bench" / "prompts" / "debug.txt"),
    ("P3", "planning", REPO_ROOT / "bench" / "prompts" / "plan.txt"),
]


async def probe_one(name: str, task_complexity: str, prompt: str) -> dict:
    role = _TASK_COMPLEXITY_TO_ROLE.get(task_complexity, "coder")
    print(f"\n=== {name} ({task_complexity} → {role}) ===", flush=True)
    print(f"prompt: {len(prompt)} chars", flush=True)

    try:
        route = await route_by_role(role, context_length=len(prompt))
    except ModelUnavailableError as exc:
        print(f"ERROR routing: {exc}", flush=True)
        return {"name": name, "ok": False, "error": str(exc)}

    print(
        f"routed: backend={route.backend} model={route.model} "
        f"base_url={route.base_url} max_tokens={route.max_tokens}",
        flush=True,
    )

    # OpenAI-compat completion. base_url already includes /v1.
    url = f"{route.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": route.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": route.max_tokens,
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    # Neither vLLM nor Ollama enforces auth on our setup, but LiteLLM
    # sends Bearer anyway; harmless to include.
    if route.backend == "vllm":
        headers["Authorization"] = "Bearer vllm"

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except Exception as exc:
        print(f"ERROR HTTP: {type(exc).__name__}: {exc}", flush=True)
        return {"name": name, "ok": False, "error": f"http: {exc}"}
    elapsed = time.time() - t0

    if resp.status_code != 200:
        print(f"ERROR status={resp.status_code} body={resp.text[:400]}", flush=True)
        return {
            "name": name,
            "ok": False,
            "status": resp.status_code,
            "error": resp.text[:400],
        }

    body = resp.json()
    choice = (body.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    usage = body.get("usage") or {}
    print(
        f"OK: elapsed={elapsed:.1f}s completion_chars={len(content)} "
        f"prompt_tokens={usage.get('prompt_tokens')} "
        f"completion_tokens={usage.get('completion_tokens')} "
        f"finish={choice.get('finish_reason')}",
        flush=True,
    )
    # Print first 200 chars of the completion so a human can eyeball quality.
    print(f"preview: {content[:200]!r}", flush=True)
    return {
        "name": name,
        "ok": True,
        "role": route.role,
        "backend": route.backend,
        "model": route.model,
        "elapsed_s": elapsed,
        "completion_chars": len(content),
        "finish_reason": choice.get("finish_reason"),
    }


async def main() -> int:
    results: list[dict] = []
    for name, task_complexity, path in PROMPTS:
        prompt = path.read_text(encoding="utf-8")
        results.append(await probe_one(name, task_complexity, prompt))

    print("\n=== SUMMARY ===", flush=True)
    for r in results:
        if r["ok"]:
            print(
                f"{r['name']} OK  role={r['role']} backend={r['backend']} "
                f"model={r['model']} elapsed={r['elapsed_s']:.1f}s "
                f"chars={r['completion_chars']} finish={r['finish_reason']}",
                flush=True,
            )
        else:
            print(f"{r['name']} FAIL {r.get('error')}", flush=True)

    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
