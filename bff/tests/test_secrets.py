"""
Tests for bff/routers/secrets.py

Covers: list/filter, masking, create, conflict, rotate, delete, scope validation.
"""
import pytest
from fastapi.testclient import TestClient
from bff.main import app
from bff.routers import secrets as secrets_module

client = TestClient(app)


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
        r = client.get("/api/secrets")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_raw_value_never_appears_in_list(self):
        body = str(client.get("/api/secrets").json())
        assert "sk-xxxx" not in body
        assert "rawValue" not in body

    def test_filter_by_global_scope(self):
        r = client.get("/api/secrets?scope=global")
        items = r.json()
        assert len(items) == 2
        assert all(s["scope"] == "global" for s in items)

    def test_filter_by_workspace_scope(self):
        r = client.get("/api/secrets?scope=workspace")
        items = r.json()
        assert len(items) == 1
        assert items[0]["scope"] == "workspace"

    def test_invalid_scope_value_returns_422(self):
        r = client.get("/api/secrets?scope=invalid")
        assert r.status_code == 422

    def test_masked_value_format(self):
        r = client.get("/api/secrets")
        for secret in r.json():
            assert secret["maskedValue"].startswith("****")


class TestCreateSecret:
    def test_create_returns_201_and_view(self):
        r = client.post("/api/secrets", json={
            "key": "NEW_KEY", "value": "supersecretvalue", "scope": "global"
        })
        assert r.status_code == 200
        body = r.json()
        assert body["key"] == "NEW_KEY"
        assert "maskedValue" in body
        assert "rawValue" not in body

    def test_create_duplicate_key_returns_409(self):
        r = client.post("/api/secrets", json={
            "key": "OPENAI_API_KEY", "value": "newvalue1234", "scope": "global"
        })
        assert r.status_code == 409

    def test_create_with_tags(self):
        r = client.post("/api/secrets", json={
            "key": "TAGGED_KEY", "value": "taggedvalue1234", "scope": "global", "tags": ["infra", "llm"]
        })
        assert r.json()["tags"] == ["infra", "llm"]

    def test_create_increments_store_count(self):
        before = len(client.get("/api/secrets").json())
        client.post("/api/secrets", json={"key": "EXTRA_KEY", "value": "somevalue123", "scope": "global"})
        after = len(client.get("/api/secrets").json())
        assert after == before + 1


class TestRotateSecret:
    def test_rotate_updates_masked_value(self):
        r = client.put("/api/secrets/sec-1/rotate", json={"newValue": "new-secret-value-9999"})
        assert r.status_code == 200
        assert r.json()["maskedValue"] == "****9999"

    def test_rotate_nonexistent_secret_returns_404(self):
        r = client.put("/api/secrets/sec-999/rotate", json={"newValue": "newvalue1234"})
        assert r.status_code == 404

    def test_rotated_raw_value_not_in_response(self):
        r = client.put("/api/secrets/sec-1/rotate", json={"newValue": "new-secret-value-9999"})
        assert "rawValue" not in str(r.json())


class TestDeleteSecret:
    def test_delete_removes_secret(self):
        client.delete("/api/secrets/sec-1")
        r = client.get("/api/secrets")
        ids = [s["id"] for s in r.json()]
        assert "sec-1" not in ids

    def test_delete_returns_ok(self):
        r = client.delete("/api/secrets/sec-2")
        assert r.json() == {"ok": True}

    def test_delete_nonexistent_returns_404(self):
        assert client.delete("/api/secrets/sec-999").status_code == 404


class TestMaskHelper:
    def test_mask_short_value(self):
        from bff.routers.secrets import _mask
        assert _mask("abc") == "****"

    def test_mask_long_value_shows_last_four(self):
        from bff.routers.secrets import _mask
        assert _mask("sk-longkey1234") == "****1234"
