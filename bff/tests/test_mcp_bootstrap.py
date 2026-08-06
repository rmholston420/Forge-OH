"""Tests for bff.services.mcp_bootstrap (Stage 4.4).

Verifies the Serena registration coroutine is idempotent, respects the
SERENA_ENABLED flag, hits `POST /api/mcp` with the exact upstream verb,
and NEVER raises (best-effort — startup must survive bootstrap failure).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from bff.services.mcp_bootstrap import (
    SERENA_SERVER_ID,
    _build_serena_registration_body,
    register_serena_if_missing,
)
from bff.settings import Settings


def _settings(**overrides: Any) -> Settings:
    """Build a fresh Settings with sensible defaults so bff.settings LRU
    doesn't leak between tests."""
    base = {
        "serena_enabled": True,
        "serena_workspace_default": "/tmp/ws",
        "serena_pin_sha": "c7af2c09ef45faa4367c0e2a9f770fb73a62a612",
        "bff_host": "127.0.0.1",
        "bff_port": 18081,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestBuildRegistrationBody:
    def test_uses_uvx_stdio_verb_with_ide_assistant_context(self):
        body = _build_serena_registration_body(_settings())
        assert body["name"] == "serena"
        assert body["transport"] == "stdio"
        assert body["command"] == "uvx"
        assert body["args"][:2] == ["--from", "git+https://github.com/oraios/serena@c7af2c09ef45faa4367c0e2a9f770fb73a62a612"]
        assert "start-mcp-server" in body["args"]
        assert body["args"][-4:] == ["--context", "ide-assistant", "--project", "/tmp/ws"]

    def test_enabled_true_by_default_on_registration(self):
        body = _build_serena_registration_body(_settings())
        assert body["enabled"] is True

    def test_description_carries_pin_sha_and_workspace(self):
        body = _build_serena_registration_body(_settings())
        assert "c7af2c09" in body["description"]
        assert "/tmp/ws" in body["description"]


class TestRegisterSerenaIfMissing:
    """These tests stub the BFF's own /api/mcp with an httpx MockTransport
    so we exercise the exact code path but don't need a live server."""

    @pytest.mark.asyncio
    async def test_returns_disabled_when_flag_off(self, monkeypatch):
        called = {"count": 0}

        def transport_handler(request: httpx.Request) -> httpx.Response:
            called["count"] += 1
            return httpx.Response(200, json=[])

        monkeypatch.setattr(
            "bff.services.mcp_bootstrap._bff_client",
            _mock_client_factory(transport_handler),
        )
        settings = _settings(serena_enabled=False)
        result = await register_serena_if_missing(settings)
        assert result == "disabled"
        assert called["count"] == 0  # no HTTP calls when disabled

    @pytest.mark.asyncio
    async def test_registers_when_missing(self, monkeypatch):
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "GET" and request.url.path == "/api/mcp":
                return httpx.Response(200, json=[{"id": "other", "name": "other"}])
            if request.method == "POST" and request.url.path == "/api/mcp":
                return httpx.Response(200, json={"id": "serena", "name": "serena"})
            return httpx.Response(404)

        monkeypatch.setattr(
            "bff.services.mcp_bootstrap._bff_client",
            _mock_client_factory(handler),
        )
        result = await register_serena_if_missing(_settings())
        assert result == "registered"
        assert ("GET", "/api/mcp") in calls
        assert ("POST", "/api/mcp") in calls

    @pytest.mark.asyncio
    async def test_skips_when_already_registered(self, monkeypatch):
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "GET" and request.url.path == "/api/mcp":
                return httpx.Response(
                    200, json=[{"id": SERENA_SERVER_ID, "name": "serena"}]
                )
            # POST should never fire
            return httpx.Response(500)

        monkeypatch.setattr(
            "bff.services.mcp_bootstrap._bff_client",
            _mock_client_factory(handler),
        )
        result = await register_serena_if_missing(_settings())
        assert result == "already_registered"
        assert all(c[0] != "POST" for c in calls)

    @pytest.mark.asyncio
    async def test_swallows_network_error(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        monkeypatch.setattr(
            "bff.services.mcp_bootstrap._bff_client",
            _mock_client_factory(handler),
        )
        result = await register_serena_if_missing(_settings())
        assert result.startswith("error:exception-")

    @pytest.mark.asyncio
    async def test_reports_post_failure(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json=[])
            return httpx.Response(422, text="bad body")

        monkeypatch.setattr(
            "bff.services.mcp_bootstrap._bff_client",
            _mock_client_factory(handler),
        )
        result = await register_serena_if_missing(_settings())
        assert result == "error:post-422"


def _mock_client_factory(handler):
    """Return an async factory matching mcp_bootstrap._bff_client's shape."""

    async def factory(base_url: str) -> httpx.AsyncClient:
        transport = httpx.MockTransport(handler)
        return httpx.AsyncClient(base_url=base_url, transport=transport, timeout=10.0)

    return factory
