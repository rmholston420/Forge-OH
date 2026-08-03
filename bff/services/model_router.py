"""Model Router — configurable primary/fallback routing between Ollama and vLLM.

The frontend NEVER selects models — all routing happens here in the BFF.
Never go below Q4_K_M quantization.

The router returns a backend-tagged model string (``ollama/<tag>`` or
``vllm/<tag>``). The caller that builds an OpenHands
``POST /api/conversations`` request body is responsible for translating that
into the LiteLLM config block the agent-server expects, e.g. for an Ollama
result::

    {"model": f"openai/{tag}",
     "base_url": OLLAMA_BASE_URL,
     "api_key": "ollama",
     "usage_id": "colossus-ollama",
     "is_subscription": False,
     "native_tool_calling": False}

Endpoints
---------
- ``OLLAMA_URL`` (default ``http://localhost:11434``) — used for the
  ``/api/tags`` health probe.
- ``OLLAMA_BASE_URL`` (default ``http://localhost:11434/v1``) — used by
  callers for OpenAI-compatible requests.
- ``VLLM_URL`` (default ``http://localhost:8500``) — vLLM OpenAI-compatible
  root; the health probe hits ``{VLLM_URL}/health``.

Primary backend
---------------
``LLM_PRIMARY_BACKEND`` (default ``ollama``) selects which backend to try
first. When set to ``vllm``, vLLM is probed first and Ollama becomes the
fallback. The other-side probe is only attempted if the primary side is
unhealthy — meaning the fallback backend can be entirely absent and normal
routing still succeeds.
"""

from __future__ import annotations

import os

import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover — dotenv is a hard dep in requirements
    load_dotenv = None  # type: ignore[assignment]

# Load .env at import time so os.getenv() sees the same values pydantic-settings
# reads. Without this, bff.settings.Settings() finds LLM_PRIMARY_BACKEND via
# .env but this module's os.getenv() calls do not, because pydantic-settings
# never exports parsed values into os.environ. The BFF cwd is the repo root
# (see scripts/forge-up.sh), which is where .env lives.
if load_dotenv is not None:  # pragma: no branch
    load_dotenv(dotenv_path=".env", override=False)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8500")

# Primary backend selection: "ollama" (default) or "vllm".
# When "vllm", vLLM is probed first and Ollama is the fallback.
LLM_PRIMARY_BACKEND = os.getenv("LLM_PRIMARY_BACKEND", "ollama").lower()

# Primary — OpenHands-recommended local model (docs.openhands.dev), MoE 3B active.
PRIMARY_MODEL = os.getenv("OLLAMA_PRIMARY_MODEL", "qwen3.6:35b-a3b")
# Fast — speed-priority fallback for low-complexity / long-context routes.
FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "qwen3-coder:30b")
# Alt — manual higher-quality dense model. Not selected automatically;
# a caller may pass task_complexity="alt" to force this route.
ALT_MODEL = os.getenv("OLLAMA_ALT_MODEL", "qwen3.6:27b")

# vLLM served-model name — must match the ``--served-model-name`` passed to
# ``vllm serve``. Used both when vLLM is the primary and when it is the
# fallback.
VLLM_FALLBACK_MODEL = os.getenv("VLLM_FALLBACK_MODEL", "qwen3-coder-30b")

# KV-cache threshold above which we route to the fast/long-context path.
# Set conservatively for qwen3.6:35b-a3b at Ollama's default 32K context.
# Adjust if you raise the num_ctx on the Ollama modelfile.
PRIMARY_CTX_LIMIT = int(os.getenv("PRIMARY_CTX_LIMIT", "28000"))


class ModelUnavailableError(RuntimeError):
    pass


async def ollama_health_check(model: str) -> bool:
    """Return True iff Ollama is reachable and has a model whose name shares
    the requested ``model``'s pre-colon prefix (e.g. ``qwen3.6``)."""
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
    """Return True iff vLLM is *ready to serve*.

    vLLM's ``/health`` returns 200 as soon as the FastAPI app is up but
    before weights are loaded; probing ``/v1/models`` instead confirms the
    engine finished loading and can accept inference. See the vLLM readiness
    guidance (llm-d.ai/docs/readiness-probes and
    docs.vllm.ai/serving/online_serving).
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{VLLM_URL}/v1/models")
            if resp.status_code != 200:
                return False
            try:
                data = resp.json().get("data", [])
            except Exception:
                return False
            return len(data) > 0
    except Exception:
        return False


async def try_model(primary: str, fallback: str | None = None) -> str:
    """Try the configured primary backend first, then fall back to the other.

    Args:
        primary: Ollama model name (e.g. ``qwen3.6:35b-a3b``). Used only for
            the Ollama-side probe; ignored when Ollama is not consulted.
        fallback: vLLM served-model name (e.g. ``qwen3-coder-30b``). Defaults
            to ``VLLM_FALLBACK_MODEL``.

    Returns:
        ``"ollama/<tag>"`` or ``"vllm/<tag>"``.

    Raises:
        ModelUnavailableError: neither backend is healthy.
    """
    resolved_fallback = fallback or VLLM_FALLBACK_MODEL

    if LLM_PRIMARY_BACKEND == "vllm":
        if await vllm_health_check():
            return f"vllm/{resolved_fallback}"
        if await ollama_health_check(primary):
            return f"ollama/{primary}"
    else:
        if await ollama_health_check(primary):
            return f"ollama/{primary}"
        if await vllm_health_check():
            return f"vllm/{resolved_fallback}"

    raise ModelUnavailableError(
        "No local LLM available. Ensure Ollama or vLLM is running."
    )


async def route_request(task_complexity: str, context_length: int) -> str:
    """Route to the optimal local model based on complexity and context length.

    task_complexity values:
      - ``"agentic"`` (default) — primary MoE model, best throughput/quality balance.
      - ``"fast"``              — speed-priority fallback (long context, low complexity).
      - ``"alt"``               — manual higher-quality dense model (requires pull).

    Long-context inputs (> ``PRIMARY_CTX_LIMIT``) are always routed to the
    fast model regardless of complexity, because the primary MoE model has no
    KV-cache headroom above its default 32K context window.
    """
    if context_length > PRIMARY_CTX_LIMIT:
        return await try_model(FAST_MODEL)
    if task_complexity == "alt":
        return await try_model(ALT_MODEL)
    if task_complexity == "agentic":
        return await try_model(PRIMARY_MODEL)
    return await try_model(FAST_MODEL)
