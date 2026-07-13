"""Tests for bff/routers/agent_presets.py."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers.agent_presets import router, _PRESETS
from bff.routers import auth as auth_router

app = FastAPI()
app.include_router(auth_router.router, prefix="/api")
app.include_router(router, prefix="/api")

anon_client = TestClient(app, raise_server_exceptions=False)


def _auth_headers() -> dict:
    body = anon_client.post(
        "/api/auth/demo-login",
        json={"username": "admin", "password": "password"},
    ).json()
    return {"Authorization": f"Bearer {body['token']}"}


def _create(name: str = "Test Preset", **kwargs) -> dict:
    payload = {"name": name, **kwargs}
    return anon_client.post("/api/agent-presets", json=payload, headers=_auth_headers()).json()


# ---------------------------------------------------------------------------
# GET /api/agent-presets  — no auth required
# ---------------------------------------------------------------------------

class TestListPresets:
    def test_returns_200(self):
        assert anon_client.get("/api/agent-presets").status_code == 200

    def test_returns_list(self):
        body = anon_client.get("/api/agent-presets").json()
        assert isinstance(body, list)

    def test_seed_data_present(self):
        body = anon_client.get("/api/agent-presets").json()
        assert len(body) >= 2

    def test_items_have_id(self):
        body = anon_client.get("/api/agent-presets").json()
        assert all("id" in p for p in body)


# ---------------------------------------------------------------------------
# GET /api/agent-presets/{id}  — no auth required
# ---------------------------------------------------------------------------

class TestGetPreset:
    def test_known_id_returns_200(self):
        assert anon_client.get("/api/agent-presets/ap-1").status_code == 200

    def test_unknown_id_returns_404(self):
        assert anon_client.get("/api/agent-presets/does-not-exist").status_code == 404

    def test_returned_preset_has_correct_id(self):
        body = anon_client.get("/api/agent-presets/ap-1").json()
        assert body["id"] == "ap-1"

    def test_default_preset_flag(self):
        body = anon_client.get("/api/agent-presets/ap-1").json()
        assert body["isDefault"] is True


# ---------------------------------------------------------------------------
# POST /api/agent-presets  — requires write role
# ---------------------------------------------------------------------------

class TestCreatePreset:
    def test_unauthenticated_returns_401(self):
        r = anon_client.post("/api/agent-presets", json={"name": "No Auth"})
        assert r.status_code == 401

    def test_returns_200_with_auth(self):
        r = anon_client.post("/api/agent-presets", json={"name": "New Preset"},
                             headers=_auth_headers())
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
        r = anon_client.post("/api/agent-presets", json={"name": "Bad", "model": "gpt-99"},
                             headers=_auth_headers())
        assert r.status_code == 422

    def test_missing_name_returns_422(self):
        r = anon_client.post("/api/agent-presets", json={"model": "gpt-4o"},
                             headers=_auth_headers())
        assert r.status_code == 422

    def test_preset_persisted_in_store(self):
        body = _create("Persist Check")
        assert body["id"] in _PRESETS


# ---------------------------------------------------------------------------
# PATCH /api/agent-presets/{id}  — requires write role
# ---------------------------------------------------------------------------

class TestUpdatePreset:
    def test_unauthenticated_returns_401(self):
        r = anon_client.patch("/api/agent-presets/ap-1", json={"name": "x"})
        assert r.status_code == 401

    def test_updates_name(self):
        pid = _create("Before Update")["id"]
        body = anon_client.patch(f"/api/agent-presets/{pid}", json={"name": "After Update"},
                                 headers=_auth_headers()).json()
        assert body["name"] == "After Update"

    def test_unknown_id_returns_404(self):
        r = anon_client.patch("/api/agent-presets/ghost", json={"name": "x"},
                              headers=_auth_headers())
        assert r.status_code == 404

    def test_updated_at_changes(self):
        pid = _create("Timing Check")["id"]
        before = _PRESETS[pid].updatedAt
        anon_client.patch(f"/api/agent-presets/{pid}", json={"name": "Updated"},
                          headers=_auth_headers())
        after = _PRESETS[pid].updatedAt
        assert after >= before


# ---------------------------------------------------------------------------
# DELETE /api/agent-presets/{id}  — requires write role
# ---------------------------------------------------------------------------

class TestDeletePreset:
    def test_unauthenticated_returns_401(self):
        r = anon_client.delete("/api/agent-presets/ap-1")
        assert r.status_code == 401

    def test_deletes_non_default(self):
        pid = _create("Delete Me")["id"]
        r = anon_client.delete(f"/api/agent-presets/{pid}", headers=_auth_headers())
        assert r.json()["ok"] is True
        assert pid not in _PRESETS

    def test_cannot_delete_default(self):
        r = anon_client.delete("/api/agent-presets/ap-1", headers=_auth_headers())
        assert r.status_code == 400

    def test_unknown_id_returns_404(self):
        assert anon_client.delete("/api/agent-presets/ghost",
                                  headers=_auth_headers()).status_code == 404


# ---------------------------------------------------------------------------
# POST /api/agent-presets/{id}/duplicate  — requires write role
# ---------------------------------------------------------------------------

class TestDuplicatePreset:
    def test_unauthenticated_returns_401(self):
        r = anon_client.post("/api/agent-presets/ap-1/duplicate")
        assert r.status_code == 401

    def test_returns_200(self):
        assert anon_client.post("/api/agent-presets/ap-1/duplicate",
                                headers=_auth_headers()).status_code == 200

    def test_clone_has_new_id(self):
        clone = anon_client.post("/api/agent-presets/ap-1/duplicate",
                                 headers=_auth_headers()).json()
        assert clone["id"] != "ap-1"

    def test_clone_name_has_copy_suffix(self):
        clone = anon_client.post("/api/agent-presets/ap-1/duplicate",
                                 headers=_auth_headers()).json()
        assert "copy" in clone["name"].lower()

    def test_clone_is_not_default(self):
        clone = anon_client.post("/api/agent-presets/ap-1/duplicate",
                                 headers=_auth_headers()).json()
        assert clone["isDefault"] is False

    def test_unknown_id_returns_404(self):
        assert anon_client.post("/api/agent-presets/ghost/duplicate",
                                headers=_auth_headers()).status_code == 404


# ---------------------------------------------------------------------------
# POST /api/agent-presets/{id}/set-default  — requires write role
# ---------------------------------------------------------------------------

class TestSetDefault:
    def test_unauthenticated_returns_401(self):
        r = anon_client.post("/api/agent-presets/ap-2/set-default")
        assert r.status_code == 401

    def test_sets_target_as_default(self):
        body = anon_client.post("/api/agent-presets/ap-2/set-default",
                                headers=_auth_headers()).json()
        assert body["isDefault"] is True
        assert body["id"] == "ap-2"

    def test_previous_default_cleared(self):
        anon_client.post("/api/agent-presets/ap-2/set-default", headers=_auth_headers())
        ap1 = anon_client.get("/api/agent-presets/ap-1").json()
        assert ap1["isDefault"] is False

    def test_only_one_default_exists(self):
        anon_client.post("/api/agent-presets/ap-1/set-default", headers=_auth_headers())
        all_presets = anon_client.get("/api/agent-presets").json()
        defaults = [p for p in all_presets if p["isDefault"]]
        assert len(defaults) == 1

    def test_unknown_id_returns_404(self):
        assert anon_client.post("/api/agent-presets/ghost/set-default",
                                headers=_auth_headers()).status_code == 404
