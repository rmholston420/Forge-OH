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

app = FastAPI()

# TODO(foh-phase2): restrict allow_origins to the actual frontend origin
# before any production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
app_with_sio = socketio.ASGIApp(sio, other_asgi_app=app)
