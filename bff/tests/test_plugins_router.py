"""Tests for bff/routers/plugins.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers import plugins

app = FastAPI()
app.include_router(plugins.router, prefix="/api")
client = TestClient(app)


class TestListPlugins:
    def test_returns_200(self):
        assert client.get("/api/plugins").status_code == 200

    def test_data_is_list(self):
        body = client.get("/api/plugins").json()
        payload = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(payload, list)


class TestInstallPlugin:
    PAYLOAD = {"pluginId": "plugin-fmt", "version": "1.0.0"}

    def test_returns_200_or_201(self):
        r = client.post("/api/plugins/install", json=self.PAYLOAD)
        assert r.status_code in (200, 201)

    def test_missing_plugin_id_returns_422(self):
        r = client.post("/api/plugins/install", json={"version": "1.0.0"})
        assert r.status_code == 422


class TestUninstallPlugin:
    def test_returns_200_or_404(self):
        r = client.delete("/api/plugins/plugin-fmt")
        assert r.status_code in (200, 404)

    def test_ok_or_not_found(self):
        body = client.delete("/api/plugins/plugin-fmt").json()
        assert "ok" in body or "detail" in body


class TestTogglePlugin:
    def test_enable_returns_200_or_404(self):
        r = client.post("/api/plugins/plugin-fmt/enable")
        assert r.status_code in (200, 404)

    def test_disable_returns_200_or_404(self):
        r = client.post("/api/plugins/plugin-fmt/disable")
        assert r.status_code in (200, 404)
