"""
Tests for bff/routers/auth.py

Run: pytest bff/tests/test_auth.py
"""
import pytest
from fastapi.testclient import TestClient
from bff.main import app
from bff.auth_state import _TOKENS


@pytest.fixture(autouse=True)
def clear_tokens():
    """Isolate token state between tests."""
    _TOKENS.clear()
    yield
    _TOKENS.clear()


client = TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_valid_admin_credentials_returns_token_and_user(self):
        r = client.post("/api/auth/login", json={"email": "admin@forge.dev", "password": "password123"})
        assert r.status_code == 200
        body = r.json()
        assert "token" in body
        assert len(body["token"]) == 64          # secrets.token_hex(32)
        assert body["user"]["role"] == "admin"
        assert body["user"]["email"] == "admin@forge.dev"
        # rawValue must never appear in the response
        assert "rawValue" not in str(body)

    def test_valid_developer_credentials_returns_developer_role(self):
        r = client.post("/api/auth/login", json={"email": "dev@forge.dev", "password": "password123"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "developer"

    def test_unknown_email_returns_401(self):
        r = client.post("/api/auth/login", json={"email": "nobody@forge.dev", "password": "password123"})
        assert r.status_code == 401

    def test_short_password_returns_401(self):
        r = client.post("/api/auth/login", json={"email": "admin@forge.dev", "password": "short"})
        assert r.status_code == 401

    def test_login_stores_token_in_tokens_dict(self):
        r = client.post("/api/auth/login", json={"email": "admin@forge.dev", "password": "password123"})
        token = r.json()["token"]
        assert token in _TOKENS

    def test_each_login_issues_unique_token(self):
        r1 = client.post("/api/auth/login", json={"email": "admin@forge.dev", "password": "password123"})
        r2 = client.post("/api/auth/login", json={"email": "admin@forge.dev", "password": "password123"})
        assert r1.json()["token"] != r2.json()["token"]


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    def _login(self) -> str:
        r = client.post("/api/auth/login", json={"email": "dev@forge.dev", "password": "password123"})
        return r.json()["token"]

    def test_logout_removes_token(self):
        token = self._login()
        assert token in _TOKENS
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert token not in _TOKENS

    def test_logout_returns_ok(self):
        token = self._login()
        r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.json() == {"ok": True}

    def test_logout_with_invalid_token_is_idempotent(self):
        r = client.post("/api/auth/logout", headers={"Authorization": "Bearer bogus"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_second_logout_with_same_token_is_safe(self):
        token = self._login()
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def _login(self, email="admin@forge.dev") -> str:
        r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        return r.json()["token"]

    def test_me_returns_correct_user(self):
        token = self._login("viewer@forge.dev")
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["role"] == "viewer"
        assert r.json()["email"] == "viewer@forge.dev"

    def test_me_without_token_returns_401(self):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token_returns_401(self):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert r.status_code == 401

    def test_me_after_logout_returns_401(self):
        token = self._login()
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
