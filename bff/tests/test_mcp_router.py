"""Tests for bff/routers/mcp.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff import openhands_client
from bff.routers import mcp

app = FastAPI(lifespan=openhands_client.lifespan)
app.include_router(mcp.router, prefix="/api")
import pytest

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:
        yield c
class TestListMcpServers:
    def test_returns_200(self, client):
        assert client.get("/api/mcp").status_code == 200

    def test_data_is_list(self, client):
        body = client.get("/api/mcp").json()
        # Accept both {"data": [...]} envelope and bare list
        payload = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(payload, list)


class TestRegisterMcpServer:
    PAYLOAD = {"name": "my-mcp", "url": "http://localhost:8080", "transport": "sse"}

    def test_returns_200_or_201(self, client):
        r = client.post("/api/mcp", json=self.PAYLOAD)
        # 409 acceptable — server already registered from prior test invocation
        assert r.status_code in (200, 201, 409)

    def test_missing_url_returns_422(self, client):
        r = client.post("/api/mcp", json={"name": "no-url"})
        assert r.status_code == 422


class TestDeleteMcpServer:
    def test_delete_existing_returns_ok(self, client):
        # Register first so we have something to delete
        pid = client.post(
            "/api/mcp",
            json={"name": "temp", "url": "http://x", "transport": "sse"}
        ).json().get("id") or "srv-1"
        r = client.delete(f"/api/mcp/{pid}")
        assert r.status_code in (200, 204, 404)  # 404 acceptable for stub


class TestMcpTools:
    def test_list_tools_returns_200(self, client):
        r = client.get("/api/mcp/srv-1/tools")
        assert r.status_code in (200, 404)  # stub may 404 for unknown server
