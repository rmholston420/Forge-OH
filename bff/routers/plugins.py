"""Plugins router — temporary minimal registry for Forge-OH.

The original OpenHands plugins router handled manifests, webhooks, signatures,
health pings, and SSE event streaming. Forge-OH currently only needs a small
install/list/enable/disable registry to unblock UI and tests.

TODO(foh-phase2):
- Decide on Forge-OH plugin model (manifest vs installed plugin records)
- Restore webhook/event handling or move to a different integration path
- Align auth, secrets, and lifecycle semantics with Rigpa-LMS needs

"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from bff.middleware.rbac import require_role

router = APIRouter(prefix="/plugins", tags=["plugins"])


class InstalledPlugin(BaseModel):
    pluginId: str
    version: str
    enabled: bool = True
    name: Optional[str] = None


class InstallPluginRequest(BaseModel):
    pluginId: str
    version: str


_PLUGINS: dict[str, InstalledPlugin] = {}


@router.get("")
def list_plugins(_: None = Depends(require_role("read"))):
    return list(_PLUGINS.values())


@router.post("/install")
def install_plugin(body: InstallPluginRequest, _: None = Depends(require_role("write"))):
    plugin = InstalledPlugin(pluginId=body.pluginId, version=body.version, enabled=True)
    _PLUGINS[body.pluginId] = plugin
    return plugin


@router.delete("/{plugin_id}")
def uninstall_plugin(plugin_id: str, _: None = Depends(require_role("delete"))):
    if plugin_id not in _PLUGINS:
        raise HTTPException(status_code=404, detail="Plugin not found")
    del _PLUGINS[plugin_id]
    return {"ok": True}


@router.post("/{plugin_id}/enable")
def enable_plugin(plugin_id: str, _: None = Depends(require_role("write"))):
    plugin = _PLUGINS.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    plugin.enabled = True
    return {"ok": True}


@router.post("/{plugin_id}/disable")
def disable_plugin(plugin_id: str, _: None = Depends(require_role("write"))):
    plugin = _PLUGINS.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    plugin.enabled = False
    return {"ok": True}
