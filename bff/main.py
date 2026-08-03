"""
bff/main.py

FastAPI application entry-point.

CRITICAL — two constraints that must never be changed without a migration plan:

1. The ASGI entry point is ``bff.main:app_with_sio`` (the Socket.IO ASGI
   wrapper), NOT ``bff.main:app``.  Starting uvicorn with ``bff.main:app``
   silently bypasses the Socket.IO server; all WebSocket connections fail.

2. ``--workers 1`` is intentional.  In-memory router state (secrets, mcp
   servers, plugins, etc.) is process-local.  Do not scale workers until
   state is externalised.
"""

import os
from contextlib import asynccontextmanager

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bff.deps.neo4j_driver import close_neo4j_driver
from bff.openhands_client import shutdown as oh_shutdown
from bff.openhands_client import startup as oh_startup
from bff.routers import (
    agent_presets,
    bash,
    git,
    mcp,
    metrics,
    notifications,
    observability,
    plugins,
    repograph,
    runs,
    secrets,
    settings,
    trajectories,
    workspaces,
)
from bff.services import episodic_memory, event_relay, trajectory_drain


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise shared OpenHands httpx client.
    await oh_startup()
    # Initialise shared aiosqlite connection for episodic memory.
    await episodic_memory.init_db(app)
    # Slice F.13: start the trajectory drain scheduler so records
    # written by the trajectory STOP hook (without inline indexing)
    # get embedded in the background. Best-effort: an import failure
    # of the trajectory store (e.g. sqlite path missing) must not sink
    # BFF startup.
    try:
        from bff.deps.trajectory_store import get_trajectory_store

        await trajectory_drain.start_scheduler(get_trajectory_store())
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "trajectory drain scheduler failed to start: %s", exc
        )
    yield
    # Graceful shutdown.
    await trajectory_drain.stop_scheduler()
    await event_relay.shutdown_all()
    await oh_shutdown()
    await episodic_memory.close_db(app)
    # Close the shared Neo4j driver pool if it was opened.
    close_neo4j_driver()


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

app.include_router(agent_presets.router, prefix="/api")
app.include_router(secrets.router, prefix="/api")
app.include_router(secrets.conv_secrets_router, prefix="/api")
app.include_router(mcp.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(observability.router, prefix="/api")
app.include_router(plugins.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(bash.router, prefix="/api")
app.include_router(git.router, prefix="/api")
app.include_router(repograph.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(trajectories.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Wire Socket.IO server into the event relay before any conversation task runs.
event_relay.set_sio(sio)


# -----------------------------------------------------------------------------
# Socket.IO handlers — subscribe/unsubscribe to per-conversation rooms.
# Frontend contract (src/lib/streaming/useRunStream.ts):
#   client connects with query ?conversationId=<uuid>
#   client emits 'subscribe' with {conversationId} to join a room
#   client emits 'unsubscribe' to leave
# -----------------------------------------------------------------------------


def _extract_cid(source: dict) -> str | None:
    """Accept either conversationId or runId — they are identical per the
    Stage-3 identity contract (run_id == conversation_id)."""
    return (source or {}).get("conversationId") or (source or {}).get("runId")


@sio.event
async def connect(sid, environ, auth):
    from urllib.parse import parse_qs

    params = parse_qs(environ.get("QUERY_STRING", ""))
    # parse_qs returns lists; flatten first-value.
    flat = {k: v[0] for k, v in params.items() if v}
    cid = _extract_cid(flat)
    if cid:
        await sio.enter_room(sid, f"conversationId={cid}")
        event_relay.start_relay(cid)


@sio.event
async def subscribe(sid, data):
    cid = _extract_cid(data or {})
    if cid:
        await sio.enter_room(sid, f"conversationId={cid}")
        event_relay.start_relay(cid)


@sio.event
async def unsubscribe(sid, data):
    cid = _extract_cid(data or {})
    if cid:
        await sio.leave_room(sid, f"conversationId={cid}")


# ASGI entry-point: app_with_sio wraps the FastAPI app so Socket.IO
# upgrade requests are intercepted before reaching FastAPI.
app_with_sio = socketio.ASGIApp(sio, other_asgi_app=app)
