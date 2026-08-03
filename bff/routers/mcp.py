"""MCP router — passthrough to agent-server settings + mcp/test.

Upstream (agent-server) surface used:
  GET   /api/settings                              → walk agent_settings.mcp_config
  POST  /api/settings/mcp/{name}                   → register a new server
  PATCH /api/settings/mcp/{name}                   → partial update (toggle etc.)
  DELETE /api/settings/mcp/{name}                  → remove
  POST  /api/mcp/test                              → connectivity + tool discovery

BFF surface (frontend contract — src/features/mcp/api.ts & endpoints.ts):
  GET    /api/mcp                    → McpServer[]  (bare list, no envelope)
  POST   /api/mcp                    → McpServer
  DELETE /api/mcp/{id}               → 204
  POST   /api/mcp/{id}/ping          → {ok, latencyMs, toolCount, tools?}
  POST   /api/mcp/{id}/toggle        → McpServer   (flip enabled)

Reshape upstream MCPServer + settings_key → frontend McpServer:
  id            = settings_key (name)
  name          = settings_key
  transport     = 'stdio' (command set) | 'http'/'sse' (url set, from server.transport)
  url           = server.url ?? ''
  command       = server.command
  enabled       = server.enabled
  description   = server.description
  status        = 'connected' if last ping ok else 'disconnected'
  toolCount     = last ping tool count (0 until first ping)
  tools         = last ping tools (populated after ping)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from bff.openhands_client import get_client

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ---------------------------------------------------------------------------
# In-process ping cache: {name: {status, toolCount, tools, ts}}
# Persistence beyond process lifetime is out of scope for Slice 7C.
# ---------------------------------------------------------------------------
_PING_CACHE: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Reshape
# ---------------------------------------------------------------------------


def _infer_transport(server: dict[str, Any]) -> str:
    t = server.get("transport")
    if t in ("stdio", "http", "sse"):
        return t
    if server.get("command"):
        return "stdio"
    if server.get("url"):
        # Default remote is 'http' unless the URL scheme hints at sse
        url = server.get("url", "")
        return "sse" if "sse" in url else "http"
    return "stdio"


def _reshape(name: str, server: dict[str, Any]) -> dict[str, Any]:
    cached = _PING_CACHE.get(name) or {}
    enabled = server.get("enabled", True)
    if not enabled:
        status = "disabled"
    else:
        status = cached.get("status", "disconnected")
    return {
        "id": name,
        "name": name,
        "url": server.get("url") or "",
        "transport": _infer_transport(server),
        "command": server.get("command"),
        "enabled": enabled,
        "description": server.get("description"),
        "tools": cached.get("tools", []),
        "toolCount": cached.get("toolCount", 0),
        "tags": [],
        "lastPingMs": cached.get("latencyMs"),
        "lastPingAt": cached.get("ts"),
        "status": status,
    }


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class RegisterMcpRequest(BaseModel):
    name: str
    transport: str = "stdio"  # 'stdio' | 'http' | 'sse'
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: bool = True
    description: str | None = None
    headers: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_settings() -> dict[str, Any]:
    client = get_client()
    resp = await client.get("/api/settings")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    return resp.json() or {}


async def _load_mcp_config() -> dict[str, dict[str, Any]]:
    settings = await _load_settings()
    agent = settings.get("agent_settings") or {}
    return (agent.get("mcp_config") or {}) or {}


async def _get_server_or_404(name: str) -> dict[str, Any]:
    cfg = await _load_mcp_config()
    if name not in cfg:
        raise HTTPException(status_code=404, detail=f"mcp server not found: {name}")
    return cfg[name]


def _build_upstream_server(body: RegisterMcpRequest) -> dict[str, Any]:
    """Translate our register body → agent-server MCPServer shape."""
    if body.transport == "stdio":
        if not body.command:
            raise HTTPException(status_code=422, detail="stdio transport requires 'command'")
    else:
        if not body.url:
            raise HTTPException(
                status_code=422, detail=f"{body.transport} transport requires 'url'"
            )

    out: dict[str, Any] = {
        "enabled": body.enabled,
        "transport": body.transport,
    }
    if body.url is not None:
        out["url"] = body.url
    if body.command is not None:
        out["command"] = body.command
    if body.args is not None:
        out["args"] = body.args
    if body.env is not None:
        out["env"] = body.env
    if body.headers is not None:
        out["headers"] = body.headers
    if body.description is not None:
        out["description"] = body.description
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_mcp() -> list[dict[str, Any]]:
    cfg = await _load_mcp_config()
    return [_reshape(name, server) for name, server in cfg.items()]


@router.post("")
async def register_mcp(body: RegisterMcpRequest) -> dict[str, Any]:
    upstream = _build_upstream_server(body)

    client = get_client()
    resp = await client.post(f"/api/settings/mcp/{body.name}", json=upstream)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])

    server = await _get_server_or_404(body.name)
    # Best-effort probe so first-list shows real status.
    try:
        await _probe_and_cache(body.name, server)
    except Exception:
        pass
    return _reshape(body.name, server)


@router.delete("/{server_id}", status_code=204)
async def delete_mcp(server_id: str) -> Response:
    client = get_client()
    resp = await client.delete(f"/api/settings/mcp/{server_id}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"mcp server not found: {server_id}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    _PING_CACHE.pop(server_id, None)
    return Response(status_code=204)


@router.post("/{server_id}/toggle")
async def toggle_mcp(server_id: str) -> dict[str, Any]:
    server = await _get_server_or_404(server_id)
    new_enabled = not bool(server.get("enabled", True))
    client = get_client()
    resp = await client.patch(
        f"/api/settings/mcp/{server_id}",
        json={"enabled": new_enabled},
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    updated = await _get_server_or_404(server_id)
    return _reshape(server_id, updated)


async def _probe_and_cache(name: str, server: dict[str, Any]) -> dict[str, Any]:
    """Run POST /api/mcp/test and record status+tools in cache."""
    client = get_client()
    started = time.monotonic()
    resp = await client.post(
        "/api/mcp/test",
        json={"name": name, "server": server, "timeout": 10.0},
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if resp.status_code >= 400:
        _PING_CACHE[name] = {
            "status": "error",
            "toolCount": 0,
            "tools": [],
            "latencyMs": latency_ms,
            "ts": ts,
            "error": resp.text[:200],
        }
        return _PING_CACHE[name]

    payload = resp.json() or {}
    if payload.get("ok"):
        tools = payload.get("tools") or []
        _PING_CACHE[name] = {
            "status": "connected",
            "toolCount": len(tools),
            "tools": tools,
            "latencyMs": latency_ms,
            "ts": ts,
        }
    else:
        _PING_CACHE[name] = {
            "status": "error",
            "toolCount": 0,
            "tools": [],
            "latencyMs": latency_ms,
            "ts": ts,
            "error": payload.get("error"),
        }
    return _PING_CACHE[name]


@router.post("/{server_id}/ping")
async def ping_mcp(server_id: str) -> dict[str, Any]:
    server = await _get_server_or_404(server_id)
    result = await _probe_and_cache(server_id, server)
    return {
        "ok": result["status"] == "connected",
        "latencyMs": result["latencyMs"],
        "toolCount": result["toolCount"],
        "tools": result["tools"],
    }
