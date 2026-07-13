from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timezone
import time

router = APIRouter(prefix='/mcp', tags=['mcp'])

class McpServer(BaseModel):
    id:          str
    name:        str
    description: Optional[str] = None
    transport:   Literal['stdio', 'sse', 'http']
    command:     Optional[str] = None
    url:         Optional[str] = None
    status:      Literal['connected', 'disconnected', 'error', 'connecting']
    toolCount:   int = 0
    lastPingMs:  Optional[float] = None
    lastSeenAt:  Optional[str] = None
    tags:        list[str] = []
    enabled:     bool = True

class RegisterRequest(BaseModel):
    name:        str
    transport:   Literal['stdio', 'sse', 'http']
    command:     Optional[str] = None
    url:         Optional[str] = None
    description: Optional[str] = None
    tags:        list[str] = []

def _now(): return datetime.now(timezone.utc).isoformat()

_SERVERS: dict[str, McpServer] = {
    'mcp-1': McpServer(
        id='mcp-1', name='Filesystem', transport='stdio',
        command='npx -y @modelcontextprotocol/server-filesystem /tmp',
        status='connected', toolCount=8, lastPingMs=12,
        lastSeenAt=_now(), tags=['files', 'local'],
    ),
    'mcp-2': McpServer(
        id='mcp-2', name='Brave Search', transport='http',
        url='https://api.search.brave.com/mcp',
        status='disconnected', toolCount=2, tags=['search', 'web'],
    ),
}

@router.get('', response_model=list[McpServer])
def list_servers(): return list(_SERVERS.values())

@router.post('', response_model=McpServer)
def register_server(body: RegisterRequest):
    server = McpServer(
        id=str(uuid4()), status='connecting', toolCount=0,
        **body.dict(),
    )
    _SERVERS[server.id] = server
    return server

@router.delete('/{server_id}')
def delete_server(server_id: str):
    if server_id not in _SERVERS: raise HTTPException(404, 'Server not found')
    del _SERVERS[server_id]
    return {'ok': True}

@router.post('/{server_id}/ping')
async def ping_server(server_id: str):
    server = _SERVERS.get(server_id)
    if not server: raise HTTPException(404, 'Server not found')
    start = time.monotonic()
    # Demo: simulate ping latency
    latency = int((time.monotonic() - start) * 1000) + 15
    updated = server.copy(update={'lastPingMs': latency, 'lastSeenAt': _now(),
                                   'status': 'connected'})
    _SERVERS[server_id] = updated
    return {'ok': True, 'latencyMs': latency}

@router.post('/{server_id}/toggle', response_model=McpServer)
def toggle_server(server_id: str):
    server = _SERVERS.get(server_id)
    if not server: raise HTTPException(404, 'Server not found')
    updated = server.copy(update={'enabled': not server.enabled})
    _SERVERS[server_id] = updated
    return updated
