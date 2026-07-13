from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import os

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
from bff.services.openhands_client import OpenHandsClient

app = FastAPI()
openhands_client = OpenHandsClient()

# CORS — use a specific origin in production via FRONTEND_ORIGIN env var.
# allow_credentials=True is incompatible with allow_origins=["*"] per the CORS spec;
# browsers will block all credentialed requests. We either allow a wildcard without
# credentials, or we specify exact origins with credentials. In dev, the wildcard
# without credentials is sufficient. Set FRONTEND_ORIGIN for production.
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

# CRITICAL: The canonical ASGI entry point is app_with_sio, NOT app.
# Uvicorn must be started with: uvicorn bff.main:app_with_sio
# Starting with bff.main:app silently bypasses the Socket.IO server
# and all WebSocket connections will fail.
app_with_sio = socketio.ASGIApp(sio, other_asgi_app=app)

@app.on_event("shutdown")
async def shutdown_openhands_client() -> None:
    await openhands_client.close()
