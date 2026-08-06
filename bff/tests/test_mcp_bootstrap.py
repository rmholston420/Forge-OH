"""Tests for bff.services.mcp_bootstrap (Stage 4.4, ADR-018).

Verifies the Serena registration coroutine is idempotent, respects the
SERENA_ENABLED flag, calls agent-server's `POST /api/settings/mcp/serena`
with the exact upstream verb, and NEVER raises (best-effort — startup
must survive bootstrap failure).

Design amended 2026-08-06 01:07 EDT: bootstrap talks to agent-server
directly via a shared httpx client instead of calling BFF's own
`/api/mcp`, because BFF's socket isn't bound during the lifespan
startup phase. Tests inject `client=` explicitly.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from bff.services.mcp_bootstrap import (
    SERENA_SERVER_ID,
    _build_serena_upstream_server,
    register_serena_if_missing,
)
from bff.settings import Settings


def _settings(**overrides: Any) -> Settings:
    """Build a fresh Settings so bff.settings LRU doesn't leak
    between tests."""
    base = {
        "serena_enabled": True,
        "serena_workspace_default": "/tmp/ws",
        "serena_pin_sha": "c7af2c09ef45faa4367c0e2a9f770fb73a62a612",
        "bff_host": "127.0.0.1",
        "bff_port": 18081,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _client_with_handler(handler) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient whose transport is a MockTransport
    running `handler`. Same base_url convention agent-server uses."""
    return httpx.AsyncClient(
        base_url="http://agent-server.test",
        transport=httpx.MockTransport(handler),
        timeout=10.0,
    )


class TestBuildUpstreamServer:
    def test_uses_uvx_stdio_verb_with_ide_assistant_context(self):
        body = _build_serena_upstream_server(_settings())
        assert body["transport"] == "stdio"
        assert body["command"] == "uvx"
        assert body["args"][:2] == [
            "--from",
            "git+https://github.com/oraios/serena@c7af2c09ef45faa4367c0e2a9f770fb73a62a612",
        ]
        assert "start-mcp-server" in body["args"]
        assert body["args"][-4:] == [
            "--context",
            "ide-assistant",
            "--project",
            "/tmp/ws",
        ]

    def test_enabled_true_and_name_carried_separately(self):
        """agent-server takes the name from the URL path, not the body."""
        body = _build_serena_upstream_server(_settings())
        assert body["enabled"] is True
        # Name is in the URL, not the body — matches router style.
        assert "name" not in body

    def test_description_carries_pin_sha_and_workspace(self):
        body = _build_serena_upstream_server(_settings())
        assert "c7af2c09" in body["description"]
        assert "/tmp/ws" in body["description"]


class TestRegisterSerenaIfMissing:
    @pytest.mark.asyncio
    async def test_returns_disabled_when_flag_off(self):
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            return httpx.Response(200, json={})

        async with _client_with_handler(handler) as client:
            settings = _settings(serena_enabled=False)
            result = await register_serena_if_missing(settings, client=client)
        assert result == "disabled"
        assert calls == []  # no HTTP calls when disabled

    @pytest.mark.asyncio
    async def test_registers_when_missing(self):
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "GET" and request.url.path == "/api/settings":
                return httpx.Response(
                    200,
                    json={"agent_settings": {"mcp_config": {"other": {}}}},
                )
            if (
                request.method == "POST"
                and request.url.path == f"/api/settings/mcp/{SERENA_SERVER_ID}"
            ):
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(404)

        async with _client_with_handler(handler) as client:
            result = await register_serena_if_missing(_settings(), client=client)
        assert result == "registered"
        assert ("GET", "/api/settings") in calls
        assert ("POST", f"/api/settings/mcp/{SERENA_SERVER_ID}") in calls

    @pytest.mark.asyncio
    async def test_skips_when_already_registered(self):
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "GET" and request.url.path == "/api/settings":
                return httpx.Response(
                    200,
                    json={
                        "agent_settings": {
                            "mcp_config": {SERENA_SERVER_ID: {"transport": "stdio"}}
                        }
                    },
                )
            # POST should never fire
            return httpx.Response(500)

        async with _client_with_handler(handler) as client:
            result = await register_serena_if_missing(_settings(), client=client)
        assert result == "already_registered"
        assert all(c[0] != "POST" for c in calls)

    @pytest.mark.asyncio
    async def test_handles_missing_agent_settings_block(self):
        """A brand-new agent-server may return `{}` or `{"agent_settings": null}`
        — both must be treated as 'no servers, register Serena'."""
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "GET":
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"ok": True})

        async with _client_with_handler(handler) as client:
            result = await register_serena_if_missing(_settings(), client=client)
        assert result == "registered"

    @pytest.mark.asyncio
    async def test_swallows_network_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        async with _client_with_handler(handler) as client:
            result = await register_serena_if_missing(_settings(), client=client)
        assert result.startswith("error:exception-")

    @pytest.mark.asyncio
    async def test_reports_post_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json={"agent_settings": {"mcp_config": {}}})
            return httpx.Response(422, text="bad body")

        async with _client_with_handler(handler) as client:
            result = await register_serena_if_missing(_settings(), client=client)
        assert result == "error:post-422"

    @pytest.mark.asyncio
    async def test_reports_get_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="upstream down")

        async with _client_with_handler(handler) as client:
            result = await register_serena_if_missing(_settings(), client=client)
        assert result == "error:list-500"
