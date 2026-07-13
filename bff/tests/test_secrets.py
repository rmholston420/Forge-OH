"""
Tests for bff/routers/secrets.py

Covers: list/filter, masking, create, conflict, rotate, delete, scope validation.

All requests to /api/secrets require Authorization because _require_auth is
called unconditionally in every handler.
"""
import pytest
from fastapi.testclient import TestClient
from bff.main import app
from bff.routers import secrets as secrets_module
from bff.auth_state import _TOKENS

# Seed a valid token for the duration of the module.
_TEST_TOKEN = "test-secrets-token"
_TOKENS[_TEST_TOKEN] = "1"  # user-id "1" is sufficient; secrets router only checks token existence

client = TestClient(app)


def _auth() -> dict:
    """Return auth headers for every secrets request."""
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def reset_store():
    """Restore the in-memory store after every test."""
    import copy
    original = copy.deepcopy(secrets_module._STORE)
    yield
    secrets_module._STORE.clear()
    secrets_module._STORE.update(original)


class TestListSecrets:
    def test_returns_all_three_seed_secrets(self):
        r = client.get("/api/secrets", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()["data"]) == 3

    def test_unauthenticated_returns_401(self):
        r = client.get("/api/secrets")
        assert r.status_code == 401

    def test_raw_value_never_appears_in_list(self):
        body = str(client.get("/api/secrets", headers=_auth()).json())
        assert "rawValue" not in body

    def test_filter_by_global_scope(self):
        items = client.get("/api/secrets", headers=_auth(), params={"scope": "global"}).json()["data"]
        assert len(items) == 2
        assert all(s["scope"] == "global" for s in items)

    def test_filter_by_workspace_scope(self):
        items = client.get("/api/secrets", headers=_auth(), params={"scope": "workspace"}).json()["data"]
        assert len(items) == 1
        assert items[0]["scope"] == "workspace"

    def test_invalid_scope_value_returns_422(self):
        r = client.get("/api/secrets", headers=_auth(), params={"scope": "invalid"})
        assert r.status_code == 422

    def test_masked_value_format(self):
        items = client.get("/api/secrets", headers=_auth()).json()["data"]
        for secret in items:
            assert secret["maskedValue"].startswith("****")


class TestCreateSecret:
    def test_create_returns_200_and_view(self):
        r = client.post("/api/secrets", headers=_auth(), json={
            "key": "NEW_KEY", "value": "supersecretvalue", "scope": "global"
        })
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["key"] == "NEW_KEY"
        assert "maskedValue" in body
        assert "rawValue" not in body

    def test_unauthenticated_returns_401(self):
        r = client.post("/api/secrets", json={"key": "X", "value": "y", "scope": "global"})
        assert r.status_code == 401

    def test_create_duplicate_key_returns_409(self):
        r = client.post("/api/secrets", headers=_auth(), json={
            "key": "OPENAI_API_KEY", "value": "newvalue1234", "scope": "global"
        })
        assert r.status_code == 409

    def test_create_with_tags(self):
        r = client.post("/api/secrets", headers=_auth(), json={
            "key": "TAGGED_KEY", "value": "taggedvalue1234", "scope": "global", "tags": ["infra", "llm"]
        })
        assert r.json()["data"]["tags"] == ["infra", "llm"]

    def test_create_increments_store_count(self):
        before = len(client.get("/api/secrets", headers=_auth()).json()["data"])
        client.post("/api/secrets", headers=_auth(), json={"key": "EXTRA_KEY", "value": "somevalue123", "scope": "global"})
        after = len(client.get("/api/secrets", headers=_auth()).json()["data"])
        assert after == before + 1


class TestRotateSecret:
    def test_rotate_updates_masked_value(self):
        r = client.put("/api/secrets/sec-1/rotate", headers=_auth(), json={"newValue": "new-secret-value-9999"})
        assert r.status_code == 200
        assert r.json()["data"]["maskedValue"] == "****9999"

    def test_unauthenticated_returns_401(self):
        r = client.put("/api/secrets/sec-1/rotate", json={"newValue": "newvalue"})
        assert r.status_code == 401

    def test_rotate_nonexistent_secret_returns_404(self):
        r = client.put("/api/secrets/sec-999/rotate", headers=_auth(), json={"newValue": "newvalue1234"})
        assert r.status_code == 404

    def test_rotated_raw_value_not_in_response(self):
        r = client.put("/api/secrets/sec-1/rotate", headers=_auth(), json={"newValue": "new-secret-value-9999"})
        assert "rawValue" not in str(r.json())


class TestDeleteSecret:
    def test_delete_removes_secret(self):
        client.delete("/api/secrets/sec-1", headers=_auth())
        ids = [s["id"] for s in client.get("/api/secrets", headers=_auth()).json()["data"]]
        assert "sec-1" not in ids

    def test_unauthenticated_returns_401(self):
        r = client.delete("/api/secrets/sec-1")
        assert r.status_code == 401

    def test_delete_returns_ok(self):
        r = client.delete("/api/secrets/sec-2", headers=_auth())
        assert r.json() == {"ok": True}

    def test_delete_nonexistent_returns_404(self):
        assert client.delete("/api/secrets/sec-999", headers=_auth()).status_code == 404


class TestMaskHelper:
    def test_mask_short_value(self):
        from bff.routers.secrets import _mask
        assert _mask("abc") == "****"

    def test_mask_long_value_shows_last_four(self):
        from bff.routers.secrets import _mask
        assert _mask("sk-longkey1234") == "****1234"
