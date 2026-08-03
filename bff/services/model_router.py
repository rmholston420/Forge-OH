"""Model Router — Ollama-first, vLLM fallback routing policy.

The frontend NEVER selects models — all routing happens here in the BFF.
Never go below Q4_K_M quantization.

The router returns an Ollama-flavoured model string (`ollama/<tag>` or
`vllm/<tag>`). The caller that builds an OpenHands `POST /api/conversations`
request body is responsible for translating that into the LiteLLM config
block the agent-server expects, e.g. for an Ollama result:

    {"model": f"openai/{tag}",
     "base_url": OLLAMA_BASE_URL,
     "api_key": "ollama",
     "usage_id": "colossus-ollama",
     "is_subscription": False,
     "native_tool_calling": False}

The Ollama OpenAI-compatible endpoint lives at OLLAMA_BASE_URL (default
http://localhost:11434/v1); the /api/tags health probe uses OLLAMA_URL
(default http://localhost:11434).
"""
from __future__ import annotations

import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")

# Primary — OpenHands-recommended local model (docs.openhands.dev), MoE 3B active.
PRIMARY_MODEL = os.getenv("OLLAMA_PRIMARY_MODEL", "qwen3.6:35b-a3b")
# Fast — speed-priority fallback for low-complexity / long-context routes.
FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "qwen3-coder:30b")
# Alt — manual higher-quality dense model. Not selected automatically;
# a caller may pass task_complexity="alt" to force this route.
ALT_MODEL = os.getenv("OLLAMA_ALT_MODEL", "qwen3.6:27b")

# vLLM fallback model name — must match whatever model is loaded in vLLM.
# Previously this was the hard-coded string "vllm", which resolved to
# the nonsensical path "vllm/vllm". Now configurable via env var.
VLLM_FALLBACK_MODEL = os.getenv("VLLM_FALLBACK_MODEL", "mistral:7b")

# KV-cache threshold above which we route to the fast/long-context path.
# Set conservatively for qwen3.6:35b-a3b at Ollama's default 32K context.
# Adjust if you raise the num_ctx on the Ollama modelfile.
PRIMARY_CTX_LIMIT = int(os.getenv("PRIMARY_CTX_LIMIT", "28000"))


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
        primary: Ollama model name (e.g. 'qwen3.6:35b-a3b')
        fallback: vLLM model name (e.g. 'mistral:7b'). Defaults to VLLM_FALLBACK_MODEL.
    """
    resolved_fallback = fallback or VLLM_FALLBACK_MODEL
    if await ollama_health_check(primary):
        return f"ollama/{primary}"
    if await vllm_health_check():
        return f"vllm/{resolved_fallback}"
    raise ModelUnavailableError("No local LLM available. Ensure Ollama or vLLM is running.")


async def route_request(task_complexity: str, context_length: int) -> str:
    """Route to optimal local model based on task complexity and context length.

    task_complexity values:
      - "agentic" (default) — primary MoE model, best throughput/quality balance.
      - "fast"              — speed-priority fallback (long context, low complexity).
      - "alt"               — manual higher-quality dense model (requires pull).

    Long-context inputs (> PRIMARY_CTX_LIMIT) are always routed to the fast
    model regardless of complexity, because the primary MoE model has no
    KV-cache headroom above its default 32K context window.
    """
    if context_length > PRIMARY_CTX_LIMIT:
        return await try_model(FAST_MODEL)
    if task_complexity == "alt":
        return await try_model(ALT_MODEL)
    if task_complexity == "agentic":
        return await try_model(PRIMARY_MODEL)
    return await try_model(FAST_MODEL)
