"""Tests for bff/routers/workspaces.py."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers.workspaces import router, _WORKSPACES

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)

CREATE_PAYLOAD = {"name": "My WS", "type": "local"}


# ---------------------------------------------------------------------------
# GET /api/workspaces
# ---------------------------------------------------------------------------

class TestListWorkspaces:
    def test_returns_200(self):
        assert client.get("/api/workspaces").status_code == 200

    def test_returns_list(self):
        assert isinstance(client.get("/api/workspaces").json(), list)

    def test_seed_workspaces_present(self):
        assert len(client.get("/api/workspaces").json()) >= 2

    def test_items_have_id_and_type(self):
        for ws in client.get("/api/workspaces").json():
            assert "id" in ws and "type" in ws


# ---------------------------------------------------------------------------
# GET /api/workspaces/{id}
# ---------------------------------------------------------------------------

class TestGetWorkspace:
    def test_known_id_returns_200(self):
        assert client.get("/api/workspaces/ws-1").status_code == 200

    def test_unknown_id_returns_404(self):
        assert client.get("/api/workspaces/ghost").status_code == 404

    def test_correct_workspace_returned(self):
        body = client.get("/api/workspaces/ws-1").json()
        assert body["id"] == "ws-1"

    def test_disk_fields_present(self):
        body = client.get("/api/workspaces/ws-1").json()
        assert "diskUsageMb" in body and "diskLimitMb" in body


# ---------------------------------------------------------------------------
# POST /api/workspaces
# ---------------------------------------------------------------------------

class TestCreateWorkspace:
    def test_returns_200(self):
        assert client.post("/api/workspaces", json=CREATE_PAYLOAD).status_code == 200

    def test_initial_status_is_provisioning(self):
        body = client.post("/api/workspaces", json=CREATE_PAYLOAD).json()
        assert body["status"] == "provisioning"

    def test_initial_run_count_zero(self):
        body = client.post("/api/workspaces", json=CREATE_PAYLOAD).json()
        assert body["runCount"] == 0

    def test_name_echoed(self):
        body = client.post("/api/workspaces", json={"name": "Echo", "type": "docker"}).json()
        assert body["name"] == "Echo"

    def test_invalid_type_returns_422(self):
        r = client.post("/api/workspaces", json={"name": "Bad", "type": "kubernetes"})
        assert r.status_code == 422

    def test_missing_name_returns_422(self):
        assert client.post("/api/workspaces", json={"type": "local"}).status_code == 422

    def test_persisted_in_store(self):
        body = client.post("/api/workspaces", json=CREATE_PAYLOAD).json()
        assert body["id"] in _WORKSPACES

    def test_env_vars_accepted(self):
        payload = {**CREATE_PAYLOAD, "envVars": [{"key": "TOKEN", "value": "abc", "masked": True}]}
        body = client.post("/api/workspaces", json=payload).json()
        assert len(body["envVars"]) == 1


# ---------------------------------------------------------------------------
# PATCH /api/workspaces/{id}
# ---------------------------------------------------------------------------

class TestUpdateWorkspace:
    def _ws_id(self) -> str:
        return client.post("/api/workspaces", json=CREATE_PAYLOAD).json()["id"]

    def test_updates_name(self):
        wid = self._ws_id()
        body = client.patch(f"/api/workspaces/{wid}", json={"name": "Renamed", "type": "local"}).json()
        assert body["name"] == "Renamed"

    def test_unknown_id_returns_404(self):
        r = client.patch("/api/workspaces/ghost", json={"name": "x", "type": "local"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{id}
# ---------------------------------------------------------------------------

class TestDeleteWorkspace:
    def test_deletes_known_workspace(self):
        wid = client.post("/api/workspaces", json=CREATE_PAYLOAD).json()["id"]
        r = client.delete(f"/api/workspaces/{wid}")
        assert r.json()["ok"] is True
        assert wid not in _WORKSPACES

    def test_unknown_id_returns_404(self):
        assert client.delete("/api/workspaces/ghost").status_code == 404


# ---------------------------------------------------------------------------
# POST /api/workspaces/{id}/reset
# ---------------------------------------------------------------------------

class TestResetWorkspace:
    def test_disk_usage_reset_to_zero(self):
        body = client.post("/api/workspaces/ws-1/reset").json()
        assert body["diskUsageMb"] == 0

    def test_status_reset_to_idle(self):
        body = client.post("/api/workspaces/ws-1/reset").json()
        assert body["status"] == "idle"

    def test_unknown_id_returns_404(self):
        assert client.post("/api/workspaces/ghost/reset").status_code == 404
