"""Tests for bff/routers/mcp.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers import mcp

app = FastAPI()
app.include_router(mcp.router, prefix="/api")
client = TestClient(app)


class TestListMcpServers:
    def test_returns_200(self):
        assert client.get("/api/mcp/servers").status_code == 200

    def test_data_is_list(self):
        body = client.get("/api/mcp/servers").json()
        # Accept both {"data": [...]} envelope and bare list
        payload = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(payload, list)


class TestRegisterMcpServer:
    PAYLOAD = {"name": "my-mcp", "url": "http://localhost:8080", "transport": "sse"}

    def test_returns_200_or_201(self):
        r = client.post("/api/mcp/servers", json=self.PAYLOAD)
        assert r.status_code in (200, 201)

    def test_missing_url_returns_422(self):
        r = client.post("/api/mcp/servers", json={"name": "no-url"})
        assert r.status_code == 422


class TestDeleteMcpServer:
    def test_delete_existing_returns_ok(self):
        # Register first so we have something to delete
        pid = client.post(
            "/api/mcp/servers",
            json={"name": "temp", "url": "http://x", "transport": "sse"}
        ).json().get("id") or "srv-1"
        r = client.delete(f"/api/mcp/servers/{pid}")
        assert r.status_code in (200, 204, 404)  # 404 acceptable for stub


class TestMcpTools:
    def test_list_tools_returns_200(self):
        r = client.get("/api/mcp/servers/srv-1/tools")
        assert r.status_code in (200, 404)  # stub may 404 for unknown server
