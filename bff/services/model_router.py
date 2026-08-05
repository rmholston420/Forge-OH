"""Model Router — configurable primary/fallback routing between Ollama and vLLM.

The frontend NEVER selects models — all routing happens here in the BFF.
Never go below Q4_K_M quantization.

Role-based routing via ``route_by_role(role, context_length=0)``
(F.19.2a). Returns a ``RoleRoute`` dataclass carrying backend, model,
base_url, and max_tokens. Roles are ``"coder"`` and ``"planner"``.
Backed by the dual-port vLLM topology (ADR-009 §3a) and the
``ops/vllm_supervisor.sh`` swap-on-demand controller (F.19.1a).

The legacy ``route_request(task_complexity, context_length)`` and its
helper ``try_model`` were removed in F.19.3 after all three call
sites migrated to ``route_by_role``. taskComplexity → role mapping
now lives in ``bff/routers/runs.py::_TASK_COMPLEXITY_TO_ROLE``.

Endpoints (Ollama + generic vLLM probe)
---------------------------------------
- ``OLLAMA_URL`` (default ``http://localhost:11434``) — used for the
  ``/api/tags`` health probe and by Ollama-fallback role routes.
- ``OLLAMA_BASE_URL`` (default ``http://localhost:11434/v1``) — used by
  callers for OpenAI-compatible requests.
- ``VLLM_URL`` (default ``http://localhost:8500``) — legacy F.18 vLLM
  OpenAI-compatible root; still exported for the settings probe UI
  (``vllmHealthy``) but no longer part of live routing.

Endpoints (role-based, F.19)
----------------------------
- ``LLM_CODER_URL`` (default ``http://localhost:8501``) — coder-role vLLM
  root. Health probe hits ``{LLM_CODER_URL}/v1/models``.
- ``LLM_PLANNER_URL`` (default ``http://localhost:8511``) — planner-role
  vLLM root. Health probe hits ``{LLM_PLANNER_URL}/v1/models``.

Primary backend (settings display)
----------------------------------
``LLM_PRIMARY_BACKEND`` (default ``ollama``) is retained as a settings
display hint (``primaryBackend`` field). It no longer gates live
routing — role selection is explicit via ``route_by_role``.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

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

# ---------------------------------------------------------------------------
# F.19.2a — Role-based routing configuration.
#
# ADR-009 assignments (verified by bench/f19pre):
#   Coder role   -> qwen3.6-27b-int4-autoround on vLLM :8501, max_tokens=2048
#   Planner role -> qwen3-thinking-2507-awq on vLLM :8511, max_tokens=8192
#
# Ollama fallback:
#   Coder role   -> qwen3-coder:30b (bench cell c01 baseline, still installed).
#   Planner role -> NONE. c03 broken (Ollama enable_thinking:false silent no-op)
#                   and c05/c07 length-truncate on P3. If planner vLLM cannot
#                   be brought up, route_by_role raises ModelUnavailableError.
# ---------------------------------------------------------------------------

LLM_CODER_URL = os.getenv("LLM_CODER_URL", "http://localhost:8501")
# ADR-013 amendment #1 (2026-08-05 04:55 EDT): coder canonical flipped to
# Qwen3.6-27B INT4 AutoRound after F.1b instrumented rebench. c01 was ranked
# #1 unanimously by all 3 Council scorers (Claude Fable 5, GPT 5.6 Sol,
# Gemini 3.1 Pro) with a 39.7-point combined-average margin over 3rd place.
# Rollback: set LLM_CODER_MODEL="qwen3.6-35b-nvfp4" (ADR-009 baseline).
LLM_CODER_MODEL = os.getenv("LLM_CODER_MODEL", "qwen3.6-27b-int4-autoround")
LLM_CODER_MAX_TOKENS = int(os.getenv("LLM_CODER_MAX_TOKENS", "2048"))
# ADR-009 §2 / DEBUG_LOG 2026-08-04: the `qwen3-coder:30b` Ollama Modelfile
# ships with `num_ctx=4096`, which is too small for the self-eval smoke
# prompts (they exceed the budget mid-completion and truncate). The
# `qwen3-coder:32k` custom Modelfile (same GGUF weights, `num_ctx=32768`)
# is the working fallback. Env override retained for machines that
# haven't rebuilt the 32k Modelfile yet.
LLM_CODER_OLLAMA_FALLBACK = os.getenv(
    "LLM_CODER_OLLAMA_FALLBACK", "qwen3-coder:32k"
)

LLM_PLANNER_URL = os.getenv("LLM_PLANNER_URL", "http://localhost:8511")
# ADR-013 (2026-08-05): planner canonical flipped to DSR1-Distill-32B AWQ
# after Path E bench matrix. c12b beat c04 (previous default) within the
# 3-point tie window and ran ~4x faster (15.5s vs 60.8s plan latency).
# Rollback: set LLM_PLANNER_MODEL="qwen3-thinking-2507-awq" (ADR-009 baseline).
LLM_PLANNER_MODEL = os.getenv("LLM_PLANNER_MODEL", "deepseek-r1-distill-32b-awq")
LLM_PLANNER_MAX_TOKENS = int(os.getenv("LLM_PLANNER_MAX_TOKENS", "8192"))
# Empty string = no Ollama fallback for planner (ADR-009 rationale above).
LLM_PLANNER_OLLAMA_FALLBACK = os.getenv("LLM_PLANNER_OLLAMA_FALLBACK", "")

# Supervisor script path (F.19.1a). Router shells out to `ensure <role>` on
# health-check miss to trigger swap-on-demand per ADR-009 §3a.
# Resolved to repo-root/ops/vllm_supervisor.sh; override for tests.
_REPO_ROOT = Path(__file__).resolve().parents[2]
VLLM_SUPERVISOR_PATH = os.getenv(
    "VLLM_SUPERVISOR_PATH", str(_REPO_ROOT / "ops" / "vllm_supervisor.sh")
)
# Timeout for the supervisor's `ensure` command. Must be >= the launcher's
# weight-load time (typically 30-60s for 30B AWQ/NVFP4 on Blackwell).
# F.19.4 fix: must be strictly greater than the supervisor's own
# VLLM_READY_TIMEOUT (default 420s in ops/vllm_supervisor.sh) so we don't
# kill supervisor mid-wait. 480s = 420 + 60s slop for docker start/stop.
VLLM_SUPERVISOR_TIMEOUT = float(os.getenv("VLLM_SUPERVISOR_TIMEOUT", "480"))
# In-request cap on how long route_by_role() will block waiting for the
# supervisor. G.1 diagnosis (DEBUG_LOG 2026-08-04 00:15 EDT): a broken
# coder container wedges every POST /api/runs for the full 480s window,
# so every self-eval task hits ReadTimeout with an empty BFF log. Cap
# short (default 8s) so the request path degrades to Ollama fallback
# (coder) or a clean ModelUnavailableError (planner) instead of hanging.
# The supervisor subprocess keeps running in the background after the
# cap fires; a subsequent request will see it via _vllm_role_health().
VLLM_SUPERVISOR_REQUEST_CAP = float(
    os.getenv("VLLM_SUPERVISOR_REQUEST_CAP", "8")
)
# Set to "0" to disable the supervisor call entirely (unit tests, or when
# operating both roles manually). Router then behaves as "probe-only".
VLLM_SUPERVISOR_ENABLED = os.getenv("VLLM_SUPERVISOR_ENABLED", "1") == "1"

# Per-role lock: coalesce concurrent _supervisor_ensure() calls. Without
# this, 3 parallel self-eval tasks each spawn their own vllm_supervisor.sh
# subprocess and race against the same GPU. Lazy-init on first use so the
# module remains import-safe outside an event loop.
_SUPERVISOR_LOCKS: dict[str, asyncio.Lock] = {}


def _supervisor_lock(role: str) -> asyncio.Lock:
    lock = _SUPERVISOR_LOCKS.get(role)
    if lock is None:
        lock = asyncio.Lock()
        _SUPERVISOR_LOCKS[role] = lock
    return lock


class ModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoleRoute:
    """Resolved route for a role-based request.

    The caller builds the LiteLLM ``llm`` block from these fields directly:

        {
            "model": f"openai/{route.model}",
            "base_url": route.base_url,
            "api_key": "vllm" if route.backend == "vllm" else "ollama",
            "usage_id": f"colossus-{route.backend}",
            "is_subscription": False,
            "native_tool_calling": False,
            "max_completion_tokens": route.max_tokens,
        }
    """

    role: str          # "coder" | "planner"
    backend: str       # "vllm" | "ollama"
    model: str         # served-model-name (vLLM) or ollama tag
    base_url: str      # OpenAI-compatible root, e.g. http://localhost:8501/v1
    max_tokens: int    # max_completion_tokens for the LiteLLM llm block

    @property
    def tagged(self) -> str:
        """Backward-compat helper mirroring the legacy string API."""
        return f"{self.backend}/{self.model}"


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


# ---------------------------------------------------------------------------
# F.19.2a — Role-based routing.
# ---------------------------------------------------------------------------


async def _vllm_role_health(role_url: str) -> bool:
    """Per-role vLLM readiness probe (mirror of ``vllm_health_check`` but
    against an arbitrary URL). Confirms the engine finished weight load."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{role_url}/v1/models")
            if resp.status_code != 200:
                return False
            try:
                data = resp.json().get("data", [])
            except Exception:
                return False
            return len(data) > 0
    except Exception:
        return False


async def _supervisor_ensure(
    role: str, request_cap: float | None = None
) -> bool:
    """Ask the swap-on-demand supervisor to bring the requested role up.

    Returns True on supervisor exit 0. Disabled (returns False) when
    ``VLLM_SUPERVISOR_ENABLED=0`` or the script is missing — the caller
    then treats it the same as "supervisor could not recover", i.e.
    falls through to Ollama fallback (coder) or raises (planner).

    ``request_cap`` bounds how long THIS call will await the subprocess.
    Defaults to ``VLLM_SUPERVISOR_REQUEST_CAP`` (8s). When the cap fires,
    the subprocess is NOT killed — it keeps running in the background so
    a subsequent request can pick up the ready role via the health probe.
    Callers running outside a request path (e.g. warm-up scripts) can
    pass ``request_cap=VLLM_SUPERVISOR_TIMEOUT`` for the old behaviour.

    Concurrent calls for the same role coalesce on a per-role
    ``asyncio.Lock``. If another coroutine is already waiting on the
    supervisor when we arrive, we await the lock (respecting the same
    cap) and then return the result of a fast health probe.
    """
    if not VLLM_SUPERVISOR_ENABLED:
        return False
    if not os.path.exists(VLLM_SUPERVISOR_PATH):
        return False

    cap = VLLM_SUPERVISOR_REQUEST_CAP if request_cap is None else request_cap
    lock = _supervisor_lock(role)

    # If another task holds the lock, wait up to `cap` for it and then
    # trust the health probe rather than spawning our own subprocess.
    if lock.locked():
        try:
            await asyncio.wait_for(lock.acquire(), timeout=cap)
        except asyncio.TimeoutError:
            return False
        try:
            role_url, _, _, _ = (
                _coder_config() if role == "coder" else _planner_config()
            )
            return await _vllm_role_health(role_url)
        finally:
            lock.release()

    async with lock:
        try:
            proc = await asyncio.create_subprocess_exec(
                VLLM_SUPERVISOR_PATH,
                "ensure",
                role,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception:
            return False

        try:
            await asyncio.wait_for(proc.wait(), timeout=cap)
        except asyncio.TimeoutError:
            # Cap fired. Leave the subprocess running in the background
            # so a later request can find the role healthy. Do NOT kill
            # or the coder will never come up under load.
            return False
        except Exception:
            return False
        return proc.returncode == 0


def _coder_config() -> tuple[str, str, int, str]:
    return (
        LLM_CODER_URL,
        LLM_CODER_MODEL,
        LLM_CODER_MAX_TOKENS,
        LLM_CODER_OLLAMA_FALLBACK,
    )


def _planner_config() -> tuple[str, str, int, str]:
    return (
        LLM_PLANNER_URL,
        LLM_PLANNER_MODEL,
        LLM_PLANNER_MAX_TOKENS,
        LLM_PLANNER_OLLAMA_FALLBACK,
    )


async def route_by_role(role: str, context_length: int = 0) -> RoleRoute:
    """Resolve a role to a concrete backend + model + budget.

    ADR-009 §3a topology: only one of coder/planner vLLM is resident at a
    time. Resolution order for each role:

      1. Probe ``LLM_<ROLE>_URL/v1/models``. On success, return vLLM route
         with the role's max_tokens budget.
      2. Ask the swap-on-demand supervisor (``ops/vllm_supervisor.sh``) to
         ``ensure <role>``. Re-probe on success.
      3. Fall back to that role's Ollama model if configured (coder only
         by default; planner has no Ollama fallback per ADR-009).
      4. Raise ``ModelUnavailableError``.

    ``context_length`` is accepted for API symmetry with ``route_request``
    and future gating, but F.19.2a does not use it for role routing.
    Callers pick the role explicitly.
    """
    if role == "coder":
        role_url, role_model, max_tokens, ollama_fallback = _coder_config()
    elif role == "planner":
        role_url, role_model, max_tokens, ollama_fallback = _planner_config()
    else:
        raise ValueError(f"unknown role {role!r}; expected 'coder' or 'planner'")

    # 1) Fast path — role already live.
    if await _vllm_role_health(role_url):
        return RoleRoute(
            role=role,
            backend="vllm",
            model=role_model,
            base_url=f"{role_url}/v1",
            max_tokens=max_tokens,
        )

    # 2) Cache-miss — try to swap.
    if await _supervisor_ensure(role):
        if await _vllm_role_health(role_url):
            return RoleRoute(
                role=role,
                backend="vllm",
                model=role_model,
                base_url=f"{role_url}/v1",
                max_tokens=max_tokens,
            )

    # 3) Ollama fallback (coder only by default).
    if ollama_fallback and await ollama_health_check(ollama_fallback):
        return RoleRoute(
            role=role,
            backend="ollama",
            model=ollama_fallback,
            base_url=OLLAMA_BASE_URL,
            max_tokens=max_tokens,
        )

    # 4) No path available.
    raise ModelUnavailableError(
        f"role={role!r} unavailable: vLLM at {role_url} down, "
        f"supervisor could not recover, Ollama fallback "
        f"{'exhausted' if ollama_fallback else 'disabled'}."
    )
