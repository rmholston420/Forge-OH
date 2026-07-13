"""Model Router — Ollama-first, vLLM fallback routing policy.

The frontend NEVER selects models — all routing happens here in the BFF.
Never go below Q4_K_M quantization.
"""
from __future__ import annotations

import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")
PRIMARY_MODEL = os.getenv("OLLAMA_PRIMARY_MODEL", "devstral-small:24b")
FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "qwen3:14b")

# vLLM fallback model name — must match whatever model is loaded in vLLM.
# Previously this was the hard-coded string "vllm", which resolved to
# the nonsensical path "vllm/vllm". Now configurable via env var.
VLLM_FALLBACK_MODEL = os.getenv("VLLM_FALLBACK_MODEL", "mistral:7b")

# KV cache threshold: Devstral 24B has near-zero headroom above 28K tokens
DEVSTRAL_CTX_LIMIT = 28_000


class ModelUnavailableError(RuntimeError):
    pass


async def ollama_health_check(model: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code != 200:
                return False
            tags = resp.json().get("models", [])
            return any(m.get("name", "").startswith(model.split(":")[0]) for m in tags)
    except Exception:
        return False


async def vllm_health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{VLLM_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def try_model(primary: str, fallback: str | None = None) -> str:
    """Try Ollama first, fall back to vLLM if available.

    Args:
        primary: Ollama model name (e.g. 'devstral-small:24b')
        fallback: vLLM model name (e.g. 'mistral:7b'). Defaults to VLLM_FALLBACK_MODEL.
    """
    resolved_fallback = fallback or VLLM_FALLBACK_MODEL
    if await ollama_health_check(primary):
        return f"ollama/{primary}"
    if await vllm_health_check():
        return f"vllm/{resolved_fallback}"
    raise ModelUnavailableError("No local LLM available. Ensure Ollama or vLLM is running.")


async def route_request(task_complexity: str, context_length: int) -> str:
    """Route to optimal local model based on task complexity and context length."""
    if context_length > DEVSTRAL_CTX_LIMIT:
        # Devstral 24B has no KV cache headroom — route to Qwen3 14B or vLLM
        return await try_model(FAST_MODEL)
    if task_complexity == "agentic":
        return await try_model(PRIMARY_MODEL)
    return await try_model(FAST_MODEL)
