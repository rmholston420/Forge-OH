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


# ---------- LLM_PRIMARY_BACKEND=ollama (default) ----------


def test_ollama_primary_prefers_ollama_when_healthy(monkeypatch):
    mr = _reload_router(monkeypatch, "ollama")

    async def yes(model=None):
        return True

    monkeypatch.setattr(mr, "ollama_health_check", yes)
    monkeypatch.setattr(mr, "vllm_health_check", yes)

    result = _run(mr.try_model("qwen3.6:35b-a3b"))
    assert result == "ollama/qwen3.6:35b-a3b"


def test_ollama_primary_falls_back_to_vllm(monkeypatch):
    mr = _reload_router(monkeypatch, "ollama")

    async def no(model=None):
        return False

    async def yes():
        return True

    monkeypatch.setattr(mr, "ollama_health_check", no)
    monkeypatch.setattr(mr, "vllm_health_check", yes)

    result = _run(mr.try_model("qwen3.6:35b-a3b"))
    assert result.startswith("vllm/")


# ---------- LLM_PRIMARY_BACKEND=vllm ----------


def test_vllm_primary_prefers_vllm_when_healthy(monkeypatch):
    mr = _reload_router(monkeypatch, "vllm")

    async def yes_o(model=None):
        return True

    async def yes_v():
        return True

    monkeypatch.setattr(mr, "ollama_health_check", yes_o)
    monkeypatch.setattr(mr, "vllm_health_check", yes_v)

    result = _run(mr.try_model("qwen3.6:35b-a3b"))
    assert result.startswith("vllm/")


def test_vllm_primary_falls_back_to_ollama(monkeypatch):
    mr = _reload_router(monkeypatch, "vllm")

    async def yes_o(model=None):
        return True

    async def no_v():
        return False

    monkeypatch.setattr(mr, "ollama_health_check", yes_o)
    monkeypatch.setattr(mr, "vllm_health_check", no_v)

    result = _run(mr.try_model("qwen3.6:35b-a3b"))
    assert result == "ollama/qwen3.6:35b-a3b"


# ---------- Both down ----------


@pytest.mark.parametrize("primary_backend", ["ollama", "vllm"])
def test_both_backends_down_raises(monkeypatch, primary_backend):
    mr = _reload_router(monkeypatch, primary_backend)

    async def no_o(model=None):
        return False

    async def no_v():
        return False

    monkeypatch.setattr(mr, "ollama_health_check", no_o)
    monkeypatch.setattr(mr, "vllm_health_check", no_v)

    with pytest.raises(mr.ModelUnavailableError):
        _run(mr.try_model("qwen3.6:35b-a3b"))


# ---------- Fallback model override ----------


def test_explicit_fallback_model_overrides_env_default(monkeypatch):
    mr = _reload_router(monkeypatch, "ollama")

    async def no(model=None):
        return False

    async def yes():
        return True

    monkeypatch.setattr(mr, "ollama_health_check", no)
    monkeypatch.setattr(mr, "vllm_health_check", yes)

    result = _run(mr.try_model("qwen3.6:35b-a3b", fallback="explicit-vllm-tag"))
    assert result == "vllm/explicit-vllm-tag"


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
