from fastapi.testclient import TestClient

from bff.main import app


client = TestClient(app)


def test_get_settings():
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] in {"system", "light", "dark"}
    assert "keyboardShortcuts" in body


def test_patch_settings():
    resp = client.patch("/api/settings", json={"theme": "dark", "fontSize": "lg"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "dark"
    assert body["fontSize"] == "lg"


def test_reset_settings():
    client.patch("/api/settings", json={"theme": "dark"})
    resp = client.post("/api/settings/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "system"


def test_model_routing_endpoint():
    resp = client.get("/api/settings/model-routing")
    assert resp.status_code == 200
    body = resp.json()
    # Legacy F.18 fields (kept for FE compat).
    assert "ollamaUrl" in body
    assert "vllmUrl" in body
    assert "primaryBackend" in body
    assert body["primaryBackend"] in {"ollama", "vllm"}
    assert "primaryModel" in body
    assert "fastModel" in body
    assert "vllmModel" in body
    assert "ollamaPrimaryHealthy" in body
    assert "ollamaFastHealthy" in body
    assert "vllmHealthy" in body
    assert "probes" in body
    assert len(body["probes"]) == 3
    # F.19.2c: per-role fields.
    for k in (
        "coderUrl", "coderModel", "coderMaxTokens", "coderVllmHealthy",
        "plannerUrl", "plannerModel", "plannerMaxTokens", "plannerVllmHealthy",
        "roleProbes",
    ):
        assert k in body, f"missing role field: {k}"
    assert isinstance(body["coderMaxTokens"], int) and body["coderMaxTokens"] > 0
    assert isinstance(body["plannerMaxTokens"], int) and body["plannerMaxTokens"] > 0
    role_probes = body["roleProbes"]
    assert isinstance(role_probes, list) and len(role_probes) == 2
    roles_seen = {p["role"] for p in role_probes}
    assert roles_seen == {"coder", "planner"}
    for p in role_probes:
        assert "role" in p
        # Either fully resolved (backend+model set) or error-populated.
        assert (p.get("backend") and p.get("model")) or p.get("error")
