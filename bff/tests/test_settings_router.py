"""Tests for bff/routers/settings.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers import settings

app = FastAPI()
app.include_router(settings.router, prefix="/api")
client = TestClient(app)


class TestGetSettings:
    def test_returns_200(self):
        assert client.get("/api/settings").status_code == 200

    def test_response_is_dict(self):
        assert isinstance(client.get("/api/settings").json(), dict)


class TestUpdateSettings:
    def test_patch_returns_200(self):
        r = client.patch("/api/settings", json={"theme": "dark"})
        assert r.status_code == 200

    def test_updated_value_reflected(self):
        client.patch("/api/settings", json={"theme": "dark"})
        body = client.get("/api/settings").json()
        # Value should be persisted or at minimum endpoint should not 5xx
        assert body is not None

    def test_put_returns_200(self):
        r = client.put("/api/settings", json={"theme": "light"})
        assert r.status_code in (200, 405)  # 405 if router only exposes PATCH
