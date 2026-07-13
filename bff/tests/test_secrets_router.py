"""Unit tests for bff/routers/secrets.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from bff.tests.utils import create_test_client
from bff.routers import secrets

client = create_test_client()


def _auth_headers() -> dict[str, str]:
    body = client.post(
        "/api/auth/demo-login",
        json={"username": "admin", "password": "password"},
    ).json()
    return {"Authorization": f"Bearer {body['token']}"}


class TestListSecrets:
    def test_authed_returns_200(self):
        r = client.get("/api/secrets", headers=_auth_headers())
        assert r.status_code == 200

    def test_unauthed_returns_401(self):
        # list_secrets requires auth — unauthenticated requests must be rejected.
        r = client.get("/api/secrets")
        assert r.status_code == 401

    def test_data_is_list(self):
        body = client.get("/api/secrets", headers=_auth_headers()).json()
        assert isinstance(body["data"], list)

    def test_scope_filter_global(self):
        r = client.get("/api/secrets", headers=_auth_headers(), params={"scope": "global"})
        assert r.status_code == 200

    def test_scope_filter_workspace(self):
        r = client.get("/api/secrets", headers=_auth_headers(), params={"scope": "workspace"})
        assert r.status_code == 200

    def test_scope_filter_run(self):
        r = client.get("/api/secrets", headers=_auth_headers(), params={"scope": "run"})
        assert r.status_code == 200

    def test_invalid_scope_returns_422(self):
        r = client.get("/api/secrets", headers=_auth_headers(), params={"scope": "INVALID"})
        assert r.status_code == 422


class TestCreateSecret:
    PAYLOAD = {"key": "MY_KEY", "rawValue": "s3cr3t", "scope": "global"}

    def test_authed_returns_200(self):
        r = client.post("/api/secrets", headers=_auth_headers(), json=self.PAYLOAD)
        assert r.status_code in (200, 409)  # 409 if already exists from prior test run

    def test_unauthed_returns_401(self):
        r = client.post("/api/secrets", json=self.PAYLOAD)
        assert r.status_code == 401

    def test_key_echoed(self):
        # clean up first so we always get a 200
        client.delete("/api/secrets/MY_KEY", headers=_auth_headers())
        r = client.post("/api/secrets", headers=_auth_headers(), json=self.PAYLOAD)
        assert r.status_code == 200
        assert r.json()["data"]["key"] == self.PAYLOAD["key"]

    def test_raw_value_not_in_response(self):
        """rawValue must never be returned by the API."""
        client.delete("/api/secrets/MY_KEY", headers=_auth_headers())
        r = client.post("/api/secrets", headers=_auth_headers(), json=self.PAYLOAD)
        body = r.json()
        payload = body["data"] if "data" in body else body
        assert "rawValue" not in payload

    def test_missing_key_returns_422(self):
        r = client.post("/api/secrets", headers=_auth_headers(),
                        json={"rawValue": "x", "scope": "global"})
        assert r.status_code == 422


class TestDeleteSecret:
    def test_authed_returns_200(self):
        payload = {"key": "DELETE_ME", "rawValue": "val", "scope": "global"}
        client.post("/api/secrets", headers=_auth_headers(), json=payload)
        r = client.delete("/api/secrets/DELETE_ME", headers=_auth_headers())
        assert r.status_code == 200

    def test_unauthed_returns_401(self):
        r = client.delete("/api/secrets/MY_KEY")
        assert r.status_code == 401

    def test_ok_flag(self):
        payload = {"key": "DELETE_ME_2", "rawValue": "s3cr3t", "scope": "global"}
        client.post("/api/secrets", headers=_auth_headers(), json=payload)
        r = client.delete("/api/secrets/DELETE_ME_2", headers=_auth_headers())
        assert r.status_code == 200
        assert r.json().get("ok") is True
