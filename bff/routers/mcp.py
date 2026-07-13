"""MCP router — temporary simplification for Forge-OH vertical slice.

This module currently exposes a minimal MCP server registry to keep the test
suite and frontend wiring unblocked. It intentionally omits richer behavior
from upstream OpenHands (ping latency, lastSeen, enable/disable, etc.).

TODO(foh-phase2):
- Restore full MCP server model (latency, lastSeenAt, richer status)
- Reintroduce ping/toggle semantics or replace with Forge-OH-specific design
- Align routes and payloads with final Forge-OH MCP UX

"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import uuid4

from bff.middleware.rbac import require_role

router = APIRouter(prefix="/mcp", tags=["mcp"])


class McpServer(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    transport: Literal["stdio", "sse", "http"]
    command: Optional[str] = None
    url: Optional[str] = None
    status: Literal["connected", "disconnected", "error", "connecting"]
    toolCount: int = 0
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class RegisterRequest(BaseModel):
    name: str
    transport: Literal["stdio", "sse", "http"]
    command: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


_SERVERS: dict[str, McpServer] = {
    "srv-1": McpServer(
        id="srv-1",
        name="Filesystem",
        transport="stdio",
        command="npx -y @modelcontextprotocol/server-filesystem /tmp",
        status="connected",
        toolCount=8,
        tags=["files", "local"],
    )
}


@router.get("/servers")
def list_servers(_: None = Depends(require_role("read"))):
    return list(_SERVERS.values())


@router.post("/servers")
def register_server(body: RegisterRequest, _: None = Depends(require_role("write"))):
    if body.transport in ("sse", "http") and not body.url:
        raise HTTPException(status_code=422, detail="url required")
    server = McpServer(id=str(uuid4()), status="connecting", toolCount=0, **body.model_dump())
    _SERVERS[server.id] = server
    return server


@router.delete("/servers/{server_id}")
def delete_server(server_id: str, _: None = Depends(require_role("delete"))):
    if server_id not in _SERVERS:
        raise HTTPException(status_code=404, detail="Server not found")
    del _SERVERS[server_id]
    return {"ok": True}


@router.get("/servers/{server_id}/tools")
def list_tools(server_id: str, _: None = Depends(require_role("read"))):
    if server_id not in _SERVERS:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"data": []}
