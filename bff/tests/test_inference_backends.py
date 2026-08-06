"""Unit tests for the InferenceBackend health-inventory layer.

Covers:

- ``BACKEND_REGISTRY`` contains all six canonical ids in the documented
  order (the UI radio group order depends on this).
- Each adapter's ``health()`` returns a ``BackendHealth`` \u2014 never
  raises \u2014 even when the underlying transport fails.
- ``GET /api/inference-backends`` returns 200 with the expected
  envelope shape when every backend is unreachable.
- The endpoint respects registry insertion order.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from bff.services.inference_backends import BACKEND_REGISTRY, list_backends
from bff.services.inference_backends._common import (
    probe_ollama_tags,
    probe_openai_v1_models,
)
from bff.services.inference_backends.types import BackendHealth
from bff.tests.utils import create_test_client


# ---------- Registry shape ----------


def test_registry_has_all_six_canonical_ids_in_order():
    assert list(BACKEND_REGISTRY.keys()) == [
        "ollama",
        "vllm-coder",
        "vllm-planner",
        "vllm-legacy",
        "llamacpp",
        "sglang",
    ]


def test_registry_role_hints_match_stage2_plan():
    r = BACKEND_REGISTRY
    assert r["ollama"].role_hint == "any"
    assert r["vllm-coder"].role_hint == "coder"
    assert r["vllm-planner"].role_hint == "planner"
    assert r["vllm-legacy"].role_hint == "probe"
    assert r["llamacpp"].role_hint == "any"
    assert r["sglang"].role_hint == "any"


def test_registry_vllm_ports_match_router_env_defaults():
    r = BACKEND_REGISTRY
    assert r["vllm-coder"].base_url.endswith(":8501")
    assert r["vllm-planner"].base_url.endswith(":8511")
    assert r["vllm-legacy"].base_url.endswith(":8500")


# ---------- Adapter health probes never raise ----------


def _fake_client(monkeypatch, response_or_exc):
    """Patch httpx.AsyncClient to return a canned response or raise."""

    class _Ctx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):  # noqa: ARG002
            if isinstance(response_or_exc, Exception):
                raise response_or_exc
            return response_or_exc

    def _factory(*args, **kwargs):  # noqa: ARG001
        return _Ctx()

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


class _R:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body


def test_probe_openai_v1_models_healthy(monkeypatch):
    _fake_client(monkeypatch, _R(200, {"data": [{"id": "m1"}, {"id": "m2"}]}))
    h = asyncio.run(probe_openai_v1_models("http://x"))
    assert h.state == "healthy"
    assert h.model_count == 2
    assert h.error is None
    assert h.latency_ms is not None and h.latency_ms >= 0


def test_probe_openai_v1_models_degraded_when_empty(monkeypatch):
    _fake_client(monkeypatch, _R(200, {"data": []}))
    h = asyncio.run(probe_openai_v1_models("http://x"))
    assert h.state == "degraded"
    assert h.model_count == 0


def test_probe_openai_v1_models_unhealthy_on_5xx(monkeypatch):
    _fake_client(monkeypatch, _R(503))
    h = asyncio.run(probe_openai_v1_models("http://x"))
    assert h.state == "unhealthy"
    assert h.error == "HTTP 503"


def test_probe_openai_v1_models_unhealthy_on_transport_error(monkeypatch):
    _fake_client(monkeypatch, httpx.ConnectError("connection refused"))
    h = asyncio.run(probe_openai_v1_models("http://x"))
    assert h.state == "unhealthy"
    assert h.latency_ms is None
    assert "ConnectError" in (h.error or "")


def test_probe_ollama_tags_reads_models_field(monkeypatch):
    _fake_client(
        monkeypatch, _R(200, {"models": [{"name": "qwen3-coder:32k"}]})
    )
    h = asyncio.run(probe_ollama_tags("http://x"))
    assert h.state == "healthy"
    assert h.model_count == 1


# ---------- list_backends is safe with unreachable network ----------


def test_list_backends_returns_meta_for_every_registry_entry(monkeypatch):
    _fake_client(monkeypatch, httpx.ConnectError("unreachable"))
    metas = asyncio.run(list_backends())
    assert len(metas) == len(BACKEND_REGISTRY)
    ids = [m.id for m in metas]
    assert ids == list(BACKEND_REGISTRY.keys())
    for m in metas:
        assert m.health.state == "unhealthy"


# ---------- GET /api/inference-backends ----------


def test_endpoint_returns_envelope_when_all_backends_down(monkeypatch):
    _fake_client(monkeypatch, httpx.ConnectError("unreachable"))
    client = create_test_client()
    resp = client.get("/api/inference-backends")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    ids = [row["id"] for row in body["data"]]
    assert ids == list(BACKEND_REGISTRY.keys())
    for row in body["data"]:
        assert set(row.keys()) == {
            "id",
            "displayName",
            "baseUrl",
            "supportsStreaming",
            "roleHint",
            "health",
        }
        assert row["health"]["state"] == "unhealthy"
        assert row["health"]["latencyMs"] is None
        assert row["health"]["modelCount"] is None
        assert "ConnectError" in (row["health"]["error"] or "")


def test_endpoint_reports_healthy_for_backend_with_models(monkeypatch):
    """One healthy Ollama, everything else unreachable \u2014 endpoint
    reports the mixed inventory faithfully.
    """

    class _MixedCtx:
        def __init__(self, url):
            self._url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            if url.startswith("http://localhost:11434"):
                return _R(200, {"models": [{"name": "qwen3-coder:32k"}]})
            raise httpx.ConnectError("unreachable")

    def _factory(*args, **kwargs):  # noqa: ARG001
        # Return a client whose get() decides per-url what to do.
        return _MixedCtx(url="")

    monkeypatch.setattr(httpx, "AsyncClient", _factory)

    client = create_test_client()
    resp = client.get("/api/inference-backends")
    assert resp.status_code == 200
    rows = {r["id"]: r for r in resp.json()["data"]}
    assert rows["ollama"]["health"]["state"] == "healthy"
    assert rows["ollama"]["health"]["modelCount"] == 1
    for other in ["vllm-coder", "vllm-planner", "vllm-legacy", "llamacpp", "sglang"]:
        assert rows[other]["health"]["state"] == "unhealthy"
