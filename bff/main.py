"""Forge-OH BFF — FastAPI application entry point.

Start with:
    uvicorn bff.main:app_with_sio --reload

Note: Uvicorn MUST be pointed at `app_with_sio` (the Socket.IO ASGI wrapper),
not `app`, so that WebSocket connections are handled by python-socketio.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from bff.routers import runs, workspaces, mcp, observability, secrets, agents, plugins, lms
from bff.routers import auth

# Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

app = FastAPI(
    title="Forge-OH BFF",
    version="0.1.0",
    description="Backend-for-Frontend orchestration layer for Forge-OH / OpenHands.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:6006"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router,          prefix="/api", tags=["auth"])
app.include_router(runs.router,          prefix="/api", tags=["runs"])
app.include_router(workspaces.router,    prefix="/api", tags=["workspaces"])
app.include_router(mcp.router,           prefix="/api", tags=["mcp"])
app.include_router(observability.router, prefix="/api", tags=["observability"])
app.include_router(secrets.router,       prefix="/api", tags=["secrets"])
app.include_router(agents.router,        prefix="/api", tags=["agents"])
app.include_router(plugins.router,       prefix="/api", tags=["plugins"])
app.include_router(lms.router,           prefix="/api", tags=["lms"])  # Slice 5C: Rigpa-LMS

# ASGI mount for Socket.IO
# ⚠️  Run Uvicorn with:  uvicorn bff.main:app_with_sio --reload
app_with_sio = socketio.ASGIApp(sio, other_asgi_app=app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "forge-oh-bff"}


@sio.event
async def connect(sid: str, environ: dict) -> None:
    print(f"[socket] connected: {sid}")


@sio.event
async def disconnect(sid: str) -> None:
    print(f"[socket] disconnected: {sid}")
