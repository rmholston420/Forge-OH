"""
bff/main.py

FastAPI application entry-point.

CRITICAL — two constraints that must never be changed without a migration plan:

1. The ASGI entry point is ``bff.main:app_with_sio`` (the Socket.IO ASGI
   wrapper), NOT ``bff.main:app``.  Starting uvicorn with ``bff.main:app``
   silently bypasses the Socket.IO server; all WebSocket connections fail.

2. ``--workers 1`` is intentional.  The in-memory ``_TOKENS`` dict in
   ``bff/auth_state.py`` is process-local.  With multiple workers a token
   issued by worker-A will 401 on worker-B.  Replace ``_TOKENS`` with
   Redis or JWT before increasing the worker count.
"""
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from bff.routers import (
    agent_presets,
    auth,
    lms,
    mcp,
    metrics,
    notifications,
    observability,
    plugins,
    runs,
    secrets,
    settings,
    workspaces,
)
from bff.openhands_client import startup as oh_startup, shutdown as oh_shutdown
from bff.services import episodic_memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise shared OpenHands httpx client.
    await oh_startup()
    # Initialise shared aiosqlite connection for episodic memory.
    await episodic_memory.init_db(app)
    yield
    # Graceful shutdown.
    await oh_shutdown()
    await episodic_memory.close_db(app)


app = FastAPI(lifespan=lifespan)

# CORS — use a specific origin in production via FRONTEND_ORIGIN env var.
# allow_credentials=True is incompatible with allow_origins=["*"] per the
# CORS spec; browsers block credentialed requests to a wildcard origin.
# In dev the wildcard without credentials is sufficient.
# Set FRONTEND_ORIGIN for production.
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "")
_allow_origins = [_frontend_origin] if _frontend_origin else ["*"]
_allow_credentials = bool(_frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(agent_presets.router, prefix="/api")
app.include_router(lms.router, prefix="/api")
app.include_router(secrets.router, prefix="/api")
app.include_router(mcp.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(observability.router, prefix="/api")
app.include_router(plugins.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# ASGI entry-point: app_with_sio wraps the FastAPI app so Socket.IO
# upgrade requests are intercepted before reaching FastAPI.
app_with_sio = socketio.ASGIApp(sio, other_asgi_app=app)
