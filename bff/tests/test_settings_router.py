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
    assert "ollamaUrl" in body
    assert "vllmUrl" in body
    assert "primaryModel" in body
    assert "fastModel" in body
    assert "ollamaPrimaryHealthy" in body
    assert "ollamaFastHealthy" in body
    assert "vllmHealthy" in body
    assert "probes" in body
    assert len(body["probes"]) == 3
