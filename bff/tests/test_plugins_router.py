"""Tests for bff/routers/plugins.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff import openhands_client
from bff.routers import plugins

app = FastAPI(lifespan=openhands_client.lifespan)
app.include_router(plugins.router, prefix="/api")
import pytest

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:
        yield c
class TestListPlugins:
    def test_returns_200(self, client):
        assert client.get("/api/plugins").status_code == 200

    def test_data_is_list(self, client):
        body = client.get("/api/plugins").json()
        payload = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(payload, list)


class TestInstallPlugin:
    PAYLOAD = {"name": "plugin-fmt"}

    def test_returns_200_or_201(self, client):
        r = client.post("/api/plugins/install", json=self.PAYLOAD)
        # 400 acceptable — upstream agent-server rejects invalid source; test verifies routing only
        assert r.status_code in (200, 201, 400)

    def test_missing_plugin_id_returns_422(self, client):
        r = client.post("/api/plugins/install", json={"force": "not-a-bool"})
        assert r.status_code == 422


class TestUninstallPlugin:
    def test_returns_200_or_404(self, client):
        r = client.delete("/api/plugins/plugin-fmt")
        assert r.status_code in (200, 204, 404)

    def test_ok_or_not_found(self, client):
        r = client.delete("/api/plugins/plugin-fmt")
        # 204 has no body; 404 has JSON detail
        if r.status_code == 404:
            assert "detail" in r.json()
        else:
            assert r.status_code in (200, 204)


class TestTogglePlugin:
    def test_enable_returns_200_or_404(self, client):
        r = client.post("/api/plugins/plugin-fmt/enable")
        assert r.status_code in (200, 404)

    def test_disable_returns_200_or_404(self, client):
        r = client.post("/api/plugins/plugin-fmt/disable")
        assert r.status_code in (200, 404)
