import hmac, hashlib, secrets, time, asyncio
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal
from uuid import uuid4

router = APIRouter(prefix="/plugins", tags=["plugins"])

class PluginManifest(BaseModel):
    id:           str
    name:         str
    version:      str
    description:  Optional[str] = None
    baseUrl:      str
    authType:     Literal["none", "bearer", "api_key"] = "none"
    secret:       Optional[str] = None
    capabilities: list[str] = []

class RegisterPluginRequest(BaseModel):
    name:         str
    version:      str
    description:  Optional[str] = None
    baseUrl:      str
    authType:     Literal["none", "bearer", "api_key"] = "none"
    secret:       Optional[str] = None
    capabilities: list[str] = []

_PLUGINS: dict[str, PluginManifest] = {}

# Pre-register Rigpa-LMS plugin from env on startup
import os
_RIGPA_URL = os.getenv("RIGPA_PLUGIN_URL", "")
if _RIGPA_URL:
    _rigpa = PluginManifest(
        id=str(uuid4()),
        name="Rigpa-LMS",
        version="1.0.0",
        description="Rigpa Learning Management System bridge",
        baseUrl=_RIGPA_URL,
        authType="bearer",
        capabilities=[
            "run_started", "run_completed", "run_failed",
            "approval_required", "artifact_ready", "agent_message"
        ],
    )
    _PLUGINS[_rigpa.id] = _rigpa

# SSE subscribers
_sse_queues: list[asyncio.Queue] = []

@router.get("", response_model=list[PluginManifest])
def list_plugins():
    return list(_PLUGINS.values())

@router.post("", response_model=PluginManifest)
def register_plugin(body: RegisterPluginRequest):
    plugin = PluginManifest(id=str(uuid4()), **body.dict())
    _PLUGINS[plugin.id] = plugin
    return plugin

@router.delete("/{plugin_id}")
def delete_plugin(plugin_id: str):
    if plugin_id not in _PLUGINS:
        raise HTTPException(404, "Plugin not found")
    del _PLUGINS[plugin_id]
    return {"ok": True}

@router.post("/{plugin_id}/ping")
async def ping_plugin(plugin_id: str):
    plugin = _PLUGINS.get(plugin_id)
    if not plugin:
        raise HTTPException(404, "Plugin not found")
    start = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(f"{plugin.baseUrl}/health")
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"ok": True, "latencyMs": latency_ms}
    except Exception as e:
        return {"ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": str(e)}

@router.post("/webhook")
async def inbound_webhook(
    request: Request,
    x_plugin_id: str = Header(alias="X-Plugin-Id"),
    x_forge_signature: str = Header(alias="X-Forge-Signature", default=""),
):
    plugin = _PLUGINS.get(x_plugin_id)
    if not plugin:
        raise HTTPException(404, "Plugin not registered")
    body = await request.body()
    if plugin.secret:
        expected = hmac.new(plugin.secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_forge_signature):
            raise HTTPException(401, "Invalid signature")
    event = body.decode()
    for q in _sse_queues:
        await q.put(event)
    return {"ok": True}

@router.get("/events")
async def plugin_events_sse():
    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues.append(queue)
    async def generate():
        try:
            while True:
                event = await queue.get()
                yield f"data: {event}\n\n"
        finally:
            _sse_queues.remove(queue)
    return StreamingResponse(generate(), media_type="text/event-stream")
