"""Unit tests for bff/routers/auth.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import auth
from bff.auth_state import _TOKENS

app = FastAPI()
app.include_router(auth.router, prefix="/api")
client = TestClient(app)


class TestDemoLogin:
    def test_valid_credentials_return_200(self):
        r = client.post("/api/auth/demo-login", json={"username": "admin", "password": "password"})
        assert r.status_code == 200

    def test_token_in_response(self):
        body = client.post("/api/auth/demo-login", json={"username": "admin", "password": "password"}).json()
        assert "token" in body

    def test_token_registered_in_store(self):
        body = client.post("/api/auth/demo-login", json={"username": "admin", "password": "password"}).json()
        assert body["token"] in _TOKENS

    def test_user_role_returned(self):
        body = client.post("/api/auth/demo-login", json={"username": "admin", "password": "password"}).json()
        assert body["user"]["role"] in ("admin", "editor", "viewer")

    def test_invalid_password_returns_401(self):
        r = client.post("/api/auth/demo-login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_unknown_user_returns_401(self):
        r = client.post("/api/auth/demo-login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 401


class TestLogout:
    def _login(self) -> str:
        body = client.post("/api/auth/demo-login", json={"username": "admin", "password": "password"}).json()
        return body["token"]

    def test_logout_removes_token(self):
        token = self._login()
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert token not in _TOKENS

    def test_logout_returns_ok(self):
        token = self._login()
        body = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"}).json()
        assert body["ok"] is True

    def test_double_logout_is_idempotent(self):
        token = self._login()
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        # Should not raise — idempotent 200 or 401 both acceptable, just not 500
        assert r.status_code != 500
