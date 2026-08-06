"""Stage 6.5.2 tests — POST /runs/{run_id}/model (ADR-027).

Contract:
  * Only ``agentPresetId`` in the body — no raw ``model`` field, no
    ``LLM-Input`` blob (Pydantic rejects with 422).
  * Unknown preset → 404.
  * Preset with role=None → 422.
  * Preset with empty model → 422.
  * Preset model incompatible with preset role → 422.
  * Happy path → 200 + agent-server switch_llm called with a preset-
    hydrated LLM-Input, credentials never sourced from the request body.
  * Agent-server 404 (unknown conversation) → 404.
  * Agent-server 5xx → 502.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import runs
from bff.routers.agent_presets import AgentPreset

app = FastAPI()
app.include_router(runs.router, prefix="/api")
client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mk_response(status_code: int, json_body: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("POST", "http://upstream/"),
    )


class _FakeUpstream:
    """Minimal stand-in for the agent-server httpx client."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def post(
        self, url: str, *, json: dict[str, Any] | None = None, **_: Any
    ) -> httpx.Response:
        self.calls.append((url, json or {}))
        return self._response


def _mk_route(
    role: str = "coder",
    backend: str = "vllm",
    model: str = "qwen3.6-27b-int4-autoround",
    base_url: str = "http://localhost:8501",
    max_tokens: int = 2048,
) -> runs.RoleRoute:
    return runs.RoleRoute(
        role=role,
        backend=backend,
        model=model,
        base_url=base_url,
        max_tokens=max_tokens,
    )


def _mk_preset(
    *,
    id: str = "ap-1",
    name: str = "coder-canonical",
    model: str = "qwen3.6-27b-int4-autoround",
    backendId: str | None = "vllm-coder",
    role: str | None = "coder",
) -> AgentPreset:
    return AgentPreset(
        id=id,
        name=name,
        description="test",
        systemPrompt="p",
        model=model,
        backendId=backendId,
        role=role,
        maxSteps=100,
        createdAt="2026-08-06T14:00:00Z",
        updatedAt="2026-08-06T14:00:00Z",
    )


# ---------------------------------------------------------------------------
# Pydantic gate — body must contain only agentPresetId
# ---------------------------------------------------------------------------


class TestBodyContract:
    def test_missing_agent_preset_id_returns_422(self) -> None:
        r = client.post("/api/runs/run-1/model", json={})
        assert r.status_code == 422

    def test_empty_agent_preset_id_returns_422(self) -> None:
        r = client.post("/api/runs/run-1/model", json={"agentPresetId": ""})
        assert r.status_code == 422

    def test_raw_model_field_is_ignored_at_pydantic_layer(self) -> None:
        """Extra ``model`` key must NOT let the caller bypass preset
        hydration. Pydantic strips it silently; endpoint still requires
        a valid preset id."""
        r = client.post(
            "/api/runs/run-1/model",
            json={"model": "some-model", "agentPresetId": ""},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Preset lookup + validation
# ---------------------------------------------------------------------------


class TestPresetValidation:
    def test_unknown_preset_returns_404(self) -> None:
        with patch("bff.routers.agent_presets._PRESETS", {}):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "nope"},
            )
        assert r.status_code == 404
        assert "preset not found" in r.json()["detail"].lower()

    def test_preset_with_role_none_returns_422(self) -> None:
        preset = _mk_preset(id="ap-x", name="no-role", role=None)
        with patch("bff.routers.agent_presets._PRESETS", {"ap-x": preset}):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-x"},
            )
        assert r.status_code == 422
        assert "role=none" in r.json()["detail"].lower()

    def test_preset_with_empty_model_returns_422(self) -> None:
        preset = _mk_preset(id="ap-x", name="no-model", model="")
        with patch("bff.routers.agent_presets._PRESETS", {"ap-x": preset}):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-x"},
            )
        assert r.status_code == 422
        assert "empty model" in r.json()["detail"].lower()

    def test_incompatible_preset_role_model_returns_422(self) -> None:
        """Planner model paired with coder role must reject even though
        the preset itself claims role='coder'."""
        preset = _mk_preset(
            id="ap-x",
            name="mismatched",
            model="deepseek-r1-distill-32b-awq",  # planner model
            role="coder",                          # coder role — mismatch
        )
        with patch("bff.routers.agent_presets._PRESETS", {"ap-x": preset}):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-x"},
            )
        assert r.status_code == 422
        assert "preset_model_incompatible_for_role" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_forwards_preset_hydrated_llm_input_to_switch_llm(self) -> None:
        preset = _mk_preset()
        fake = _FakeUpstream(_mk_response(200, {"success": True}))
        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-1": preset}),
            patch("bff.routers.runs.get_client", return_value=fake),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(return_value=_mk_route()),
            ),
        ):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-1"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["run_id"] == "run-1"
        assert body["agentPresetId"] == "ap-1"
        assert body["resolved"]["role"] == "coder"
        assert body["resolved"]["backend"] == "vllm"
        assert body["resolved"]["model"] == "qwen3.6-27b-int4-autoround"
        assert body["resolved"]["base_url"] == "http://localhost:8501"
        assert body["resolved"]["max_tokens"] == 2048
        assert body["agent_server"] == {"success": True}

        # Wire body: agent-server switch_llm called with exactly one call,
        # correct path, LLM-Input blob under "llm" key, credentials placeholder
        # from BFF (not from client).
        assert len(fake.calls) == 1
        path, payload = fake.calls[0]
        assert path == "/api/conversations/run-1/switch_llm"
        assert set(payload.keys()) == {"llm"}
        llm = payload["llm"]
        assert llm["model"] == "openai/qwen3.6-27b-int4-autoround"
        assert llm["base_url"] == "http://localhost:8501"
        assert llm["api_key"] == "vllm"
        assert llm["max_tokens"] == 2048
        assert llm["is_subscription"] is False
        assert llm["native_tool_calling"] is False

    def test_ollama_fallback_sets_api_key_placeholder(self) -> None:
        """When the router substitutes Ollama for a coder role, the
        placeholder ``api_key`` must be ``ollama`` (not ``vllm``)."""
        preset = _mk_preset(
            id="ap-3",
            name="ollama-coder",
            model="qwen3-coder:32k",
            backendId="ollama",
        )
        fake = _FakeUpstream(_mk_response(200, {"success": True}))
        ollama_route = _mk_route(
            backend="ollama",
            model="qwen3-coder:32k",
            base_url="http://localhost:11434",
        )
        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-3": preset}),
            patch("bff.routers.runs.get_client", return_value=fake),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(return_value=ollama_route),
            ),
        ):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-3"},
            )
        assert r.status_code == 200, r.text
        _, payload = fake.calls[0]
        assert payload["llm"]["api_key"] == "ollama"
        assert payload["llm"]["base_url"] == "http://localhost:11434"

    def test_router_model_substitution_populates_resolved_model_note(self) -> None:
        """If ``route_by_role`` returns a model different from
        ``preset.model`` (Ollama fallback path in the coder catalog), the
        response must surface a ``resolved_model_note`` explaining the swap."""
        preset = _mk_preset()
        fake = _FakeUpstream(_mk_response(200, {"success": True}))
        substituted_route = _mk_route(
            backend="ollama",
            model="qwen3-coder:32k",
            base_url="http://localhost:11434",
        )
        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-1": preset}),
            patch("bff.routers.runs.get_client", return_value=fake),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(return_value=substituted_route),
            ),
        ):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-1"},
            )
        assert r.status_code == 200
        note = r.json()["resolved_model_note"]
        assert note is not None
        assert "qwen3-coder:32k" in note
        assert "qwen3.6-27b-int4-autoround" in note


# ---------------------------------------------------------------------------
# Router unavailability
# ---------------------------------------------------------------------------


class TestRouterUnavailable:
    def test_model_unavailable_error_returns_503(self) -> None:
        preset = _mk_preset()
        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-1": preset}),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(
                    side_effect=runs.ModelUnavailableError("no vllm, no ollama")
                ),
            ),
        ):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-1"},
            )
        assert r.status_code == 503
        assert "no vllm" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Agent-server error passthrough
# ---------------------------------------------------------------------------


class TestAgentServerErrors:
    def _mk_ok_preset(self) -> AgentPreset:
        return _mk_preset()

    def test_agent_server_404_returns_404(self) -> None:
        preset = self._mk_ok_preset()
        fake = _FakeUpstream(_mk_response(404, {"detail": "conversation not found"}))
        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-1": preset}),
            patch("bff.routers.runs.get_client", return_value=fake),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(return_value=_mk_route()),
            ),
        ):
            r = client.post(
                "/api/runs/no-such-run/model",
                json={"agentPresetId": "ap-1"},
            )
        assert r.status_code == 404
        assert "run not found" in r.json()["detail"].lower()

    def test_agent_server_500_returns_502(self) -> None:
        preset = self._mk_ok_preset()
        fake = _FakeUpstream(_mk_response(500, {"detail": "internal"}))
        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-1": preset}),
            patch("bff.routers.runs.get_client", return_value=fake),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(return_value=_mk_route()),
            ),
        ):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-1"},
            )
        assert r.status_code == 502
        assert "agent-server error 500" in r.json()["detail"].lower()

    def test_agent_server_transport_error_returns_502(self) -> None:
        preset = self._mk_ok_preset()

        class _RaisingUpstream:
            async def post(self, *_: Any, **__: Any) -> httpx.Response:
                raise httpx.ConnectError("connection refused")

        with (
            patch("bff.routers.agent_presets._PRESETS", {"ap-1": preset}),
            patch("bff.routers.runs.get_client", return_value=_RaisingUpstream()),
            patch(
                "bff.routers.runs.route_by_role",
                new=AsyncMock(return_value=_mk_route()),
            ),
        ):
            r = client.post(
                "/api/runs/run-1/model",
                json={"agentPresetId": "ap-1"},
            )
        assert r.status_code == 502
        assert "agent-server unreachable" in r.json()["detail"].lower()
