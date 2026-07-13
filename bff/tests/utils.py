from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import (
    auth,
    lms,
    secrets,
    mcp,
    metrics,
    notifications,
    observability,
    plugins,
    runs,
    settings,
    workspaces,
)


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router,          prefix="/api")
    app.include_router(lms.router,           prefix="/api")
    app.include_router(secrets.router,       prefix="/api")
    app.include_router(mcp.router,           prefix="/api")
    app.include_router(metrics.router,       prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(observability.router, prefix="/api")
    app.include_router(plugins.router,       prefix="/api")
    app.include_router(runs.router,          prefix="/api")
    app.include_router(settings.router,      prefix="/api")
    app.include_router(workspaces.router,    prefix="/api")
    return app


def create_test_client() -> TestClient:
    app = create_test_app()
    return TestClient(app)
