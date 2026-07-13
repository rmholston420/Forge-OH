"""
Tests for bff/middleware/rbac.py

Verifies: role resolution, rank comparisons, 401 vs 403 distinctions.
"""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from bff.middleware.rbac import require_role, LEVEL_RANK, ROLE_PERMISSIONS
from bff.auth_state import _TOKENS


@pytest.fixture(autouse=True)
def seed_tokens():
    _TOKENS.clear()
    _TOKENS["tok-admin"]     = "1"   # admin
    _TOKENS["tok-developer"] = "2"   # developer
    _TOKENS["tok-viewer"]    = "3"   # viewer
    yield
    _TOKENS.clear()


# Build a minimal app with one guarded route per level
_test_app = FastAPI()

@_test_app.get("/read-guarded")
def _read(_: None = Depends(require_role("read"))):
    return {"ok": True}

@_test_app.get("/write-guarded")
def _write(_: None = Depends(require_role("write"))):
    return {"ok": True}

@_test_app.get("/delete-guarded")
def _delete(_: None = Depends(require_role("delete"))):
    return {"ok": True}

@_test_app.get("/admin-guarded")
def _admin(_: None = Depends(require_role("admin"))):
    return {"ok": True}

tc = TestClient(_test_app)


class TestLevelRanks:
    def test_ranks_are_ordered(self):
        assert LEVEL_RANK["read"] < LEVEL_RANK["write"]
        assert LEVEL_RANK["write"] < LEVEL_RANK["delete"]
        assert LEVEL_RANK["delete"] < LEVEL_RANK["admin"]


class TestRolePermissions:
    def test_admin_has_all_levels(self):
        assert set(ROLE_PERMISSIONS["admin"]) == {"read", "write", "delete", "admin"}

    def test_developer_has_read_and_write_only(self):
        assert set(ROLE_PERMISSIONS["developer"]) == {"read", "write"}

    def test_viewer_has_read_only(self):
        assert set(ROLE_PERMISSIONS["viewer"]) == {"read"}


class TestReadEndpoint:
    def test_admin_can_read(self):
        assert tc.get("/read-guarded", headers={"Authorization": "Bearer tok-admin"}).status_code == 200

    def test_developer_can_read(self):
        assert tc.get("/read-guarded", headers={"Authorization": "Bearer tok-developer"}).status_code == 200

    def test_viewer_can_read(self):
        assert tc.get("/read-guarded", headers={"Authorization": "Bearer tok-viewer"}).status_code == 200

    def test_no_token_returns_401(self):
        assert tc.get("/read-guarded").status_code == 401

    def test_bad_token_returns_401(self):
        assert tc.get("/read-guarded", headers={"Authorization": "Bearer bad"}).status_code == 401


class TestWriteEndpoint:
    def test_admin_can_write(self):
        assert tc.get("/write-guarded", headers={"Authorization": "Bearer tok-admin"}).status_code == 200

    def test_developer_can_write(self):
        assert tc.get("/write-guarded", headers={"Authorization": "Bearer tok-developer"}).status_code == 200

    def test_viewer_cannot_write_returns_403(self):
        assert tc.get("/write-guarded", headers={"Authorization": "Bearer tok-viewer"}).status_code == 403


class TestDeleteEndpoint:
    def test_admin_can_delete(self):
        assert tc.get("/delete-guarded", headers={"Authorization": "Bearer tok-admin"}).status_code == 200

    def test_developer_cannot_delete_returns_403(self):
        assert tc.get("/delete-guarded", headers={"Authorization": "Bearer tok-developer"}).status_code == 403

    def test_viewer_cannot_delete_returns_403(self):
        assert tc.get("/delete-guarded", headers={"Authorization": "Bearer tok-viewer"}).status_code == 403


class TestAdminEndpoint:
    def test_admin_can_access_admin_endpoint(self):
        assert tc.get("/admin-guarded", headers={"Authorization": "Bearer tok-admin"}).status_code == 200

    def test_developer_cannot_access_admin_returns_403(self):
        assert tc.get("/admin-guarded", headers={"Authorization": "Bearer tok-developer"}).status_code == 403

    def test_viewer_cannot_access_admin_returns_403(self):
        assert tc.get("/admin-guarded", headers={"Authorization": "Bearer tok-viewer"}).status_code == 403
