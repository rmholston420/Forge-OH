"""Plugins router — passthrough to agent-server's plugin subsystem.

Upstream surface (agent-server):
  GET    /api/plugins/installed                    → InstalledPluginsListResponse
  GET    /api/plugins/installed/{plugin_name}      → InstalledPluginResponse
  PATCH  /api/plugins/installed/{plugin_name}      → toggle enabled
  DELETE /api/plugins/installed/{plugin_name}      → uninstall
  POST   /api/plugins/install                      → install from source
  POST   /api/plugins                              → legacy install alias (kept)
  GET    /api/plugins/marketplace                  → MarketplaceCatalogResponse

BFF surface (frontend contract):
  GET    /api/plugins                         → {data: Plugin[]}
  POST   /api/plugins                         → {data: Plugin}
  POST   /api/plugins/install                 → {data: Plugin}     (alias)
  GET    /api/plugins/marketplace             → {data: MarketplacePlugin[]}
  POST   /api/plugins/{id}/enable             → {data: Plugin}
  POST   /api/plugins/{id}/disable            → {data: Plugin}
  DELETE /api/plugins/{id}                    → 204 No Content
  POST   /api/plugins/{id}/ping               → {ok, latencyMs}

Frontend `Plugin` shape (src/lib/schemas/plugin.ts):
  {id, name, version, description?, author?, status, configSchema?,
   installedAt?, updatedAt}
"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from bff.openhands_client import get_client


router = APIRouter(prefix="/plugins", tags=["plugins"])


# ---------------------------------------------------------------------------
# Reshapers: agent-server InstalledPluginResponse → frontend Plugin
# ---------------------------------------------------------------------------

def _to_plugin(u: dict[str, Any]) -> dict[str, Any]:
    """Reshape agent-server InstalledPluginResponse into a frontend `Plugin`."""
    installed_at = u.get("installed_at")
    return {
        "id": u.get("name"),
        "name": u.get("name"),
        "version": u.get("version") or "0.0.0",
        "description": u.get("description"),
        "author": None,  # upstream doesn't expose an author field
        "status": "enabled" if u.get("enabled", True) else "disabled",
        "installedAt": installed_at,
        "updatedAt": installed_at,  # upstream has no separate updatedAt
    }


def _to_marketplace(u: dict[str, Any]) -> dict[str, Any]:
    """Reshape MarketplacePluginInfo for the marketplace view."""
    return {
        "id": u.get("name"),
        "name": u.get("name"),
        "description": u.get("description"),
        "source": u.get("source"),
        "installed": bool(u.get("installed")),
        "skills": u.get("skills") or [],
    }


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class InstallBody(BaseModel):
    # Frontend may send just an id/name; we translate to the upstream {source, ref, repo_path}
    # request. Accept both shapes for compatibility.
    source: Optional[str] = None
    ref: Optional[str] = None
    repo_path: Optional[str] = None
    force: bool = False
    # Legacy shape from src/features/plugins/api.ts InstallPlugin
    id: Optional[str] = None
    name: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_installed_plugin(name: str) -> dict[str, Any]:
    client = get_client()
    resp = await client.get(f"/api/plugins/installed/{name}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"plugin not found: {name}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    return resp.json()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_plugins() -> dict[str, Any]:
    client = get_client()
    resp = await client.get("/api/plugins/installed")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    payload = resp.json() or {}
    plugins = payload.get("plugins") or []
    return {"data": [_to_plugin(p) for p in plugins]}


@router.get("/marketplace")
async def list_marketplace() -> dict[str, Any]:
    client = get_client()
    resp = await client.get("/api/plugins/marketplace")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    payload = resp.json() or {}
    plugins = payload.get("plugins") or []
    return {"data": [_to_marketplace(p) for p in plugins]}


async def _install(body: InstallBody) -> dict[str, Any]:
    """Shared install path for POST /plugins and POST /plugins/install."""
    # Determine source: explicit field takes priority; else fall back to id/name
    # (frontend legacy shape). If only id/name is provided, we treat it as the
    # plugin's local cache path — the same convention MarketplacePluginInfo uses.
    src = body.source or body.id or body.name
    if not src:
        raise HTTPException(status_code=422, detail="missing 'source' (or 'id'/'name')")

    upstream_body: dict[str, Any] = {"source": src, "force": body.force}
    if body.ref is not None:
        upstream_body["ref"] = body.ref
    if body.repo_path is not None:
        upstream_body["repo_path"] = body.repo_path

    client = get_client()
    resp = await client.post("/api/plugins/install", json=upstream_body)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    installed = resp.json() or {}
    return {"data": _to_plugin(installed)}


@router.post("")
async def install_plugin(body: InstallBody) -> dict[str, Any]:
    return await _install(body)


@router.post("/install")
async def install_plugin_alias(body: InstallBody) -> dict[str, Any]:
    return await _install(body)


@router.delete("/{plugin_id}", status_code=204)
async def uninstall_plugin(plugin_id: str) -> Response:
    client = get_client()
    resp = await client.delete(f"/api/plugins/installed/{plugin_id}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"plugin not found: {plugin_id}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    return Response(status_code=204)


async def _set_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    client = get_client()
    resp = await client.patch(
        f"/api/plugins/installed/{plugin_id}",
        json={"enabled": enabled},
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"plugin not found: {plugin_id}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    # Upstream returns UpdatePluginStateResponse. Refetch installed record so we
    # can return a full Plugin shape consistent with list/install.
    installed = await _get_installed_plugin(plugin_id)
    return {"data": _to_plugin(installed)}


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str) -> dict[str, Any]:
    return await _set_enabled(plugin_id, True)


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str) -> dict[str, Any]:
    return await _set_enabled(plugin_id, False)


@router.post("/{plugin_id}/ping")
async def ping_plugin(plugin_id: str) -> dict[str, Any]:
    """Health-check a plugin.

    Upstream has no per-plugin ping. We interpret 'ping' as: is the plugin
    installed AND enabled? Latency is measured against the installed lookup.
    """
    started = time.monotonic()
    installed = await _get_installed_plugin(plugin_id)
    latency_ms = int((time.monotonic() - started) * 1000)
    return {"ok": bool(installed.get("enabled", True)), "latencyMs": latency_ms}
