"""Unit tests for bff/services/model_router.py.

Covers the ``LLM_PRIMARY_BACKEND`` env-driven switch between Ollama-first and
vLLM-first routing, plus the fallback, both-down, and readiness-probe paths.

Health-check functions are patched directly rather than mocking httpx so the
test does not depend on network state.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest


def _reload_router(monkeypatch, primary_backend: str):
    """Reload ``bff.services.model_router`` with ``LLM_PRIMARY_BACKEND`` set."""
    monkeypatch.setenv("LLM_PRIMARY_BACKEND", primary_backend)
    import bff.services.model_router as mr

    return importlib.reload(mr)


def _run(coro):
    return asyncio.run(coro)


# ---------- LLM_PRIMARY_BACKEND normalization ----------


def test_primary_backend_env_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PRIMARY_BACKEND", "VLLM")
    import bff.services.model_router as mr

    importlib.reload(mr)
    assert mr.LLM_PRIMARY_BACKEND == "vllm"


# ---------- vllm_health_check readiness semantics ----------


class _FakeResp:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):  # noqa: ARG002 — url ignored in tests
        return self._resp


def _patch_httpx_response(monkeypatch, mr, resp: _FakeResp):
    def _factory(*args, **kwargs):  # noqa: ARG001
        return _FakeClient(resp)

    monkeypatch.setattr(mr.httpx, "AsyncClient", _factory)


def test_vllm_health_true_when_v1_models_lists_data(monkeypatch):
    mr = _reload_router(monkeypatch, "ollama")
    _patch_httpx_response(
        monkeypatch, mr, _FakeResp(200, {"data": [{"id": "qwen3-coder-30b"}]})
    )
    assert _run(mr.vllm_health_check()) is True


def test_vllm_health_false_when_data_empty(monkeypatch):
    # /health-style behavior: server up but no model loaded → not ready.
    mr = _reload_router(monkeypatch, "ollama")
    _patch_httpx_response(monkeypatch, mr, _FakeResp(200, {"data": []}))
    assert _run(mr.vllm_health_check()) is False


def test_vllm_health_false_on_non_200(monkeypatch):
    mr = _reload_router(monkeypatch, "ollama")
    _patch_httpx_response(monkeypatch, mr, _FakeResp(503))
    assert _run(mr.vllm_health_check()) is False


# ---------------------------------------------------------------------------
# F.19.2a — Role-based routing tests.
# ---------------------------------------------------------------------------


def _reload_router_for_roles(monkeypatch):
    """Reload the router with role env clean and supervisor disabled by
    default (unit tests never shell out to bash)."""
    monkeypatch.setenv("LLM_PRIMARY_BACKEND", "vllm")
    monkeypatch.setenv("VLLM_SUPERVISOR_ENABLED", "0")
    import bff.services.model_router as mr

    return importlib.reload(mr)


def test_route_by_role_rejects_unknown_role(monkeypatch):
    mr = _reload_router_for_roles(monkeypatch)
    with pytest.raises(ValueError):
        _run(mr.route_by_role("architect"))


def test_route_by_role_coder_vllm_healthy(monkeypatch):
    mr = _reload_router_for_roles(monkeypatch)

    async def probe(url):
        return url == mr.LLM_CODER_URL

    monkeypatch.setattr(mr, "_vllm_role_health", probe)

    route = _run(mr.route_by_role("coder"))
    assert route.role == "coder"
    assert route.backend == "vllm"
    assert route.model == mr.LLM_CODER_MODEL
    assert route.base_url == f"{mr.LLM_CODER_URL}/v1"
    assert route.max_tokens == mr.LLM_CODER_MAX_TOKENS
    assert route.tagged == f"vllm/{mr.LLM_CODER_MODEL}"


def test_route_by_role_planner_vllm_healthy(monkeypatch):
    mr = _reload_router_for_roles(monkeypatch)

    async def probe(url):
        return url == mr.LLM_PLANNER_URL

    monkeypatch.setattr(mr, "_vllm_role_health", probe)

    route = _run(mr.route_by_role("planner"))
    assert route.role == "planner"
    assert route.backend == "vllm"
    assert route.model == mr.LLM_PLANNER_MODEL
    assert route.max_tokens == mr.LLM_PLANNER_MAX_TOKENS


def test_route_by_role_coder_supervisor_recovers(monkeypatch):
    """vLLM initially down; supervisor.ensure returns True; probe then True."""
    monkeypatch.setenv("VLLM_SUPERVISOR_ENABLED", "1")
    mr = _reload_router_for_roles(monkeypatch)
    # Re-enable supervisor (the helper set it to 0).
    monkeypatch.setenv("VLLM_SUPERVISOR_ENABLED", "1")
    mr = importlib.reload(mr)

    calls = {"probe": 0}

    async def probe(url):
        calls["probe"] += 1
        # First probe = False (miss), second probe (post-ensure) = True.
        return calls["probe"] >= 2

    async def ensure(role):
        assert role == "coder"
        return True

    monkeypatch.setattr(mr, "_vllm_role_health", probe)
    monkeypatch.setattr(mr, "_supervisor_ensure", ensure)

    route = _run(mr.route_by_role("coder"))
    assert route.backend == "vllm"
    assert route.model == mr.LLM_CODER_MODEL
    assert calls["probe"] == 2


def test_route_by_role_coder_falls_back_to_ollama(monkeypatch):
    """vLLM down, supervisor cannot recover, Ollama fallback picks up."""
    mr = _reload_router_for_roles(monkeypatch)

    async def probe(url):
        return False

    async def ensure(role):
        return False

    async def ollama_ok(model):
        return True

    monkeypatch.setattr(mr, "_vllm_role_health", probe)
    monkeypatch.setattr(mr, "_supervisor_ensure", ensure)
    monkeypatch.setattr(mr, "ollama_health_check", ollama_ok)

    route = _run(mr.route_by_role("coder"))
    assert route.backend == "ollama"
    assert route.model == mr.LLM_CODER_OLLAMA_FALLBACK
    assert route.base_url == mr.OLLAMA_BASE_URL
    # Ollama fallback still carries the role's max_tokens budget.
    assert route.max_tokens == mr.LLM_CODER_MAX_TOKENS


def test_route_by_role_planner_no_ollama_fallback(monkeypatch):
    """Planner has no Ollama fallback per ADR-009; must raise."""
    mr = _reload_router_for_roles(monkeypatch)

    async def probe(url):
        return False

    async def ensure(role):
        return False

    async def ollama_ok(model):
        return True  # even if Ollama is up, planner has no fallback model

    monkeypatch.setattr(mr, "_vllm_role_health", probe)
    monkeypatch.setattr(mr, "_supervisor_ensure", ensure)
    monkeypatch.setattr(mr, "ollama_health_check", ollama_ok)

    with pytest.raises(mr.ModelUnavailableError) as exc:
        _run(mr.route_by_role("planner"))
    assert "planner" in str(exc.value)
    assert "disabled" in str(exc.value)  # empty fallback -> "disabled"


def test_route_by_role_planner_all_paths_dead(monkeypatch):
    mr = _reload_router_for_roles(monkeypatch)

    async def no(*args, **kwargs):
        return False

    monkeypatch.setattr(mr, "_vllm_role_health", no)
    monkeypatch.setattr(mr, "_supervisor_ensure", no)
    monkeypatch.setattr(mr, "ollama_health_check", no)

    with pytest.raises(mr.ModelUnavailableError):
        _run(mr.route_by_role("planner"))


def test_supervisor_disabled_env_short_circuits(monkeypatch):
    """VLLM_SUPERVISOR_ENABLED=0 makes _supervisor_ensure a no-op even
    when the script exists — the router falls through to Ollama."""
    mr = _reload_router_for_roles(monkeypatch)  # helper sets ENABLED=0

    async def no_vllm(url):
        return False

    async def yes_ollama(model):
        return True

    monkeypatch.setattr(mr, "_vllm_role_health", no_vllm)
    monkeypatch.setattr(mr, "ollama_health_check", yes_ollama)
    # Do NOT patch _supervisor_ensure; rely on the real function seeing
    # VLLM_SUPERVISOR_ENABLED=0 and returning False.

    route = _run(mr.route_by_role("coder"))
    assert route.backend == "ollama"


def test_route_by_role_max_tokens_env_override(monkeypatch):
    """F.19.3: LLM_CODER_MAX_TOKENS / LLM_PLANNER_MAX_TOKENS env vars
    flow through the returned RoleRoute.max_tokens."""
    monkeypatch.setenv("LLM_CODER_MAX_TOKENS", "1234")
    monkeypatch.setenv("LLM_PLANNER_MAX_TOKENS", "5678")
    mr = _reload_router_for_roles(monkeypatch)

    async def _healthy(url):
        return True

    monkeypatch.setattr(mr, "_vllm_role_health", _healthy)

    coder_route = _run(mr.route_by_role("coder"))
    assert coder_route.max_tokens == 1234
    assert coder_route.backend == "vllm"

    planner_route = _run(mr.route_by_role("planner"))
    assert planner_route.max_tokens == 5678
    assert planner_route.backend == "vllm"


def test_role_route_dataclass_is_frozen():
    from bff.services.model_router import RoleRoute

    r = RoleRoute(
        role="coder",
        backend="vllm",
        model="m",
        base_url="http://x/v1",
        max_tokens=2048,
    )
    with pytest.raises(Exception):
        r.role = "planner"  # type: ignore[misc]
