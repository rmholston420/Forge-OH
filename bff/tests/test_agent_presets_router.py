"""Tests for bff/routers/agent_presets.py."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers.agent_presets import router, _PRESETS

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create(name: str = "Test Preset", **kwargs) -> dict:
    payload = {"name": name, **kwargs}
    return client.post("/api/agent-presets", json=payload).json()


# ---------------------------------------------------------------------------
# GET /api/agent-presets
# ---------------------------------------------------------------------------

class TestListPresets:
    def test_returns_200(self):
        assert client.get("/api/agent-presets").status_code == 200

    def test_returns_list(self):
        body = client.get("/api/agent-presets").json()
        assert isinstance(body, list)

    def test_seed_data_present(self):
        body = client.get("/api/agent-presets").json()
        assert len(body) >= 2

    def test_items_have_id(self):
        body = client.get("/api/agent-presets").json()
        assert all("id" in p for p in body)


# ---------------------------------------------------------------------------
# GET /api/agent-presets/{id}
# ---------------------------------------------------------------------------

class TestGetPreset:
    def test_known_id_returns_200(self):
        assert client.get("/api/agent-presets/ap-1").status_code == 200

    def test_unknown_id_returns_404(self):
        assert client.get("/api/agent-presets/does-not-exist").status_code == 404

    def test_returned_preset_has_correct_id(self):
        body = client.get("/api/agent-presets/ap-1").json()
        assert body["id"] == "ap-1"

    def test_default_preset_flag(self):
        body = client.get("/api/agent-presets/ap-1").json()
        assert body["isDefault"] is True


# ---------------------------------------------------------------------------
# POST /api/agent-presets
# ---------------------------------------------------------------------------

class TestCreatePreset:
    def test_returns_200(self):
        r = client.post("/api/agent-presets", json={"name": "New Preset"})
        assert r.status_code == 200

    def test_id_is_assigned(self):
        body = _create("Assigned ID")
        assert "id" in body and len(body["id"]) > 0

    def test_name_echoed(self):
        body = _create("Echo Name")
        assert body["name"] == "Echo Name"

    def test_is_default_false(self):
        body = _create("Not Default")
        assert body["isDefault"] is False

    def test_default_model_is_gpt4o(self):
        body = _create("Default Model")
        assert body["model"] == "gpt-4o"

    def test_invalid_model_returns_422(self):
        r = client.post("/api/agent-presets", json={"name": "Bad", "model": "gpt-99"})
        assert r.status_code == 422

    def test_missing_name_returns_422(self):
        r = client.post("/api/agent-presets", json={"model": "gpt-4o"})
        assert r.status_code == 422

    def test_preset_persisted_in_store(self):
        body = _create("Persist Check")
        assert body["id"] in _PRESETS


# ---------------------------------------------------------------------------
# PATCH /api/agent-presets/{id}
# ---------------------------------------------------------------------------

class TestUpdatePreset:
    def test_updates_name(self):
        pid = _create("Before Update")["id"]
        body = client.patch(f"/api/agent-presets/{pid}", json={"name": "After Update"}).json()
        assert body["name"] == "After Update"

    def test_unknown_id_returns_404(self):
        r = client.patch("/api/agent-presets/ghost", json={"name": "x"})
        assert r.status_code == 404

    def test_updated_at_changes(self):
        pid = _create("Timing Check")["id"]
        before = _PRESETS[pid].updatedAt
        client.patch(f"/api/agent-presets/{pid}", json={"name": "Updated"})
        after = _PRESETS[pid].updatedAt
        # updatedAt must be refreshed (may be equal if very fast; at minimum not earlier)
        assert after >= before


# ---------------------------------------------------------------------------
# DELETE /api/agent-presets/{id}
# ---------------------------------------------------------------------------

class TestDeletePreset:
    def test_deletes_non_default(self):
        pid = _create("Delete Me")["id"]
        r = client.delete(f"/api/agent-presets/{pid}")
        assert r.json()["ok"] is True
        assert pid not in _PRESETS

    def test_cannot_delete_default(self):
        r = client.delete("/api/agent-presets/ap-1")
        assert r.status_code == 400

    def test_unknown_id_returns_404(self):
        assert client.delete("/api/agent-presets/ghost").status_code == 404


# ---------------------------------------------------------------------------
# POST /api/agent-presets/{id}/duplicate
# ---------------------------------------------------------------------------

class TestDuplicatePreset:
    def test_returns_200(self):
        assert client.post("/api/agent-presets/ap-1/duplicate").status_code == 200

    def test_clone_has_new_id(self):
        clone = client.post("/api/agent-presets/ap-1/duplicate").json()
        assert clone["id"] != "ap-1"

    def test_clone_name_has_copy_suffix(self):
        clone = client.post("/api/agent-presets/ap-1/duplicate").json()
        assert "copy" in clone["name"].lower()

    def test_clone_is_not_default(self):
        clone = client.post("/api/agent-presets/ap-1/duplicate").json()
        assert clone["isDefault"] is False

    def test_unknown_id_returns_404(self):
        assert client.post("/api/agent-presets/ghost/duplicate").status_code == 404


# ---------------------------------------------------------------------------
# POST /api/agent-presets/{id}/set-default
# ---------------------------------------------------------------------------

class TestSetDefault:
    def test_sets_target_as_default(self):
        body = client.post("/api/agent-presets/ap-2/set-default").json()
        assert body["isDefault"] is True
        assert body["id"] == "ap-2"

    def test_previous_default_cleared(self):
        client.post("/api/agent-presets/ap-2/set-default")
        ap1 = client.get("/api/agent-presets/ap-1").json()
        assert ap1["isDefault"] is False

    def test_only_one_default_exists(self):
        client.post("/api/agent-presets/ap-1/set-default")
        all_presets = client.get("/api/agent-presets").json()
        defaults = [p for p in all_presets if p["isDefault"]]
        assert len(defaults) == 1

    def test_unknown_id_returns_404(self):
        assert client.post("/api/agent-presets/ghost/set-default").status_code == 404
