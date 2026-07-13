"""Unit tests for bff/routers/secrets.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from bff.routers import secrets
from bff.auth_state import _TOKENS

app = FastAPI()
app.include_router(secrets.router, prefix="/api")
client = TestClient(app)

# Grab any valid token from the demo token store
VALID_TOKEN = next(iter(_TOKENS))
AUTH = {"Authorization": f"Bearer {VALID_TOKEN}"}


class TestListSecrets:
    def test_authed_returns_200(self):
        r = client.get("/api/secrets", headers=AUTH)
        assert r.status_code == 200

    def test_unauthed_returns_401(self):
        r = client.get("/api/secrets")
        assert r.status_code == 401

    def test_data_is_list(self):
        body = client.get("/api/secrets", headers=AUTH).json()
        assert isinstance(body["data"], list)

    def test_scope_filter_global(self):
        r = client.get("/api/secrets", headers=AUTH, params={"scope": "global"})
        assert r.status_code == 200

    def test_scope_filter_workspace(self):
        r = client.get("/api/secrets", headers=AUTH, params={"scope": "workspace"})
        assert r.status_code == 200

    def test_scope_filter_run(self):
        r = client.get("/api/secrets", headers=AUTH, params={"scope": "run"})
        assert r.status_code == 200

    def test_invalid_scope_returns_422(self):
        r = client.get("/api/secrets", headers=AUTH, params={"scope": "INVALID"})
        assert r.status_code == 422


class TestCreateSecret:
    PAYLOAD = {"key": "MY_KEY", "rawValue": "s3cr3t", "scope": "global"}

    def test_authed_returns_200(self):
        r = client.post("/api/secrets", headers=AUTH, json=self.PAYLOAD)
        assert r.status_code == 200

    def test_unauthed_returns_401(self):
        r = client.post("/api/secrets", json=self.PAYLOAD)
        assert r.status_code == 401

    def test_key_echoed(self):
        body = client.post("/api/secrets", headers=AUTH, json=self.PAYLOAD).json()
        assert body["data"]["key"] == "MY_KEY"

    def test_raw_value_not_in_response(self):
        """rawValue must never be returned by the API."""
        body = client.post("/api/secrets", headers=AUTH, json=self.PAYLOAD).json()
        assert "rawValue" not in body["data"]

    def test_missing_key_returns_422(self):
        r = client.post("/api/secrets", headers=AUTH, json={"rawValue": "x", "scope": "global"})
        assert r.status_code == 422


class TestDeleteSecret:
    def test_authed_returns_200(self):
        r = client.delete("/api/secrets/MY_KEY", headers=AUTH)
        assert r.status_code == 200

    def test_unauthed_returns_401(self):
        r = client.delete("/api/secrets/MY_KEY")
        assert r.status_code == 401

    def test_ok_flag(self):
        body = client.delete("/api/secrets/MY_KEY", headers=AUTH).json()
        assert body["ok"] is True
