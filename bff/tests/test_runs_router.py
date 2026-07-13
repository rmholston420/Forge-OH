"""Unit tests for bff/routers/runs.py using FastAPI TestClient."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from bff.routers import runs

app = FastAPI()
app.include_router(runs.router, prefix="/api")
client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper: authenticated client (bypass RBAC for lifecycle action tests)
# ---------------------------------------------------------------------------

def _auth_client():
    """Returns a TestClient with a pre-seeded auth token for write-role tests."""
    from bff.auth_state import _TOKENS, _DEMO_USERS
    token = "test-dev-token"
    # seed a developer token so require_role("write") passes
    _TOKENS[token] = "2"  # id=2 is role=developer
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


auth_client = _auth_client()


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------

class TestListRuns:
    def test_returns_200(self):
        r = client.get("/api/runs")
        assert r.status_code == 200

    def test_data_is_list(self):
        body = client.get("/api/runs").json()
        assert isinstance(body["data"], list)

    def test_stub_flag(self):
        body = client.get("/api/runs").json()
        assert body.get("stub") is True


# ---------------------------------------------------------------------------
# POST /api/runs
# ---------------------------------------------------------------------------

CREATE_PAYLOAD = {
    "title": "My Run",
    "agentPresetId": "preset-abc",
    "workspaceId": "ws-001",
}


class TestCreateRun:
    def test_returns_200(self):
        r = auth_client.post("/api/runs", json=CREATE_PAYLOAD)
        assert r.status_code == 200

    def test_id_present(self):
        body = auth_client.post("/api/runs", json=CREATE_PAYLOAD).json()
        assert body["data"]["id"] == "run-new-001"

    def test_title_echoed(self):
        body = auth_client.post("/api/runs", json=CREATE_PAYLOAD).json()
        assert body["data"]["title"] == "My Run"

    def test_initial_status_is_queued(self):
        body = auth_client.post("/api/runs", json=CREATE_PAYLOAD).json()
        assert body["data"]["status"] == "queued"

    def test_workspace_id_echoed(self):
        body = auth_client.post("/api/runs", json=CREATE_PAYLOAD).json()
        assert body["data"]["workspaceId"] == "ws-001"

    def test_optional_context_prompt_accepted(self):
        payload = {**CREATE_PAYLOAD, "contextPrompt": "Do the thing"}
        r = auth_client.post("/api/runs", json=payload)
        assert r.status_code == 200

    def test_missing_required_field_returns_422(self):
        r = auth_client.post("/api/runs", json={"title": "No preset"})
        assert r.status_code == 422

    def test_unauthenticated_returns_401(self):
        r = client.post("/api/runs", json=CREATE_PAYLOAD)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}
# ---------------------------------------------------------------------------

class TestGetRun:
    def test_returns_200(self):
        r = client.get("/api/runs/run-001")
        assert r.status_code == 200

    def test_run_id_echoed(self):
        body = client.get("/api/runs/run-xyz").json()
        assert body["run_id"] == "run-xyz"

    def test_stub_flag(self):
        body = client.get("/api/runs/run-001").json()
        assert body.get("stub") is True


# ---------------------------------------------------------------------------
# Sub-resource stubs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sub", ["events", "plan", "files", "artifacts", "commands", "traces"])
class TestRunSubResources:
    def test_returns_200(self, sub):
        r = client.get(f"/api/runs/run-001/{sub}")
        assert r.status_code == 200

    def test_data_is_list(self, sub):
        body = client.get(f"/api/runs/run-001/{sub}").json()
        assert isinstance(body["data"], list)


class TestRunFileDiff:
    def test_returns_200(self):
        r = client.get("/api/runs/run-001/files/src/main.py")
        assert r.status_code == 200

    def test_path_echoed(self):
        body = client.get("/api/runs/run-001/files/src/main.py").json()
        assert body["path"] == "src/main.py"

    def test_nested_path_accepted(self):
        r = client.get("/api/runs/run-001/files/a/b/c.ts")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Lifecycle actions — pause / resume / stop / approve / reject
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action,expected_status", [
    ("pause",   "paused"),
    ("resume",  "running"),
    ("stop",    "stopped"),
    ("approve", "running"),
    ("reject",  "paused"),
])
class TestRunLifecycleActions:
    def test_ok_flag(self, action, expected_status):
        r = auth_client.post(f"/api/runs/run-001/{action}")
        assert r.json()["ok"] is True

    def test_status_value(self, action, expected_status):
        body = auth_client.post(f"/api/runs/run-001/{action}").json()
        assert body["status"] == expected_status

    def test_run_id_echoed(self, action, expected_status):
        body = auth_client.post(f"/api/runs/run-xzy/{action}").json()
        assert body["run_id"] == "run-xzy"

    def test_unauthenticated_returns_401(self, action, expected_status):
        r = client.post(f"/api/runs/run-001/{action}")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/fork
# ---------------------------------------------------------------------------

class TestForkRun:
    def test_returns_ok(self):
        body = auth_client.post("/api/runs/run-abc/fork").json()
        assert body["ok"] is True

    def test_forked_id_contains_base_id(self):
        body = auth_client.post("/api/runs/run-abc/fork").json()
        assert "run-abc" in body["forked_id"]

    def test_unauthenticated_returns_401(self):
        r = client.post("/api/runs/run-abc/fork")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/runs/compare
# ---------------------------------------------------------------------------

class TestCompareRuns:
    def test_returns_200(self):
        r = client.get("/api/runs/compare", params={"base": "run-aaa", "fork": "run-bbb"})
        assert r.status_code == 200

    def test_base_id_echoed(self):
        body = client.get("/api/runs/compare", params={"base": "run-aaa", "fork": "run-bbb"}).json()
        assert body["data"]["baseRunId"] == "run-aaa"

    def test_fork_id_echoed(self):
        body = client.get("/api/runs/compare", params={"base": "run-aaa", "fork": "run-bbb"}).json()
        assert body["data"]["forkRunId"] == "run-bbb"

    def test_stats_shape(self):
        body = client.get("/api/runs/compare", params={"base": "a", "fork": "b"}).json()
        stats = body["data"]["stats"]
        assert "totalFiles" in stats and "additions" in stats and "deletions" in stats

    def test_missing_base_returns_422(self):
        r = client.get("/api/runs/compare", params={"fork": "run-bbb"})
        assert r.status_code == 422

    def test_missing_fork_returns_422(self):
        r = client.get("/api/runs/compare", params={"base": "run-aaa"})
        assert r.status_code == 422
