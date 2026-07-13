"""Tests for bff/routers/observability.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers import observability

app = FastAPI()
app.include_router(observability.router, prefix="/api")
client = TestClient(app)


class TestListTraces:
    def test_returns_200(self):
        r = client.get("/api/observability/traces")
        assert r.status_code == 200

    def test_data_is_list(self):
        body = client.get("/api/observability/traces").json()
        payload = body.get("data", body) if isinstance(body, dict) else body
        assert isinstance(payload, list)


class TestGetTrace:
    def test_returns_200_or_404(self):
        r = client.get("/api/observability/traces/trace-001")
        assert r.status_code in (200, 404)


class TestListSpans:
    def test_returns_200_or_404(self):
        r = client.get("/api/observability/traces/trace-001/spans")
        assert r.status_code in (200, 404)


class TestRunTrace:
    """Observability endpoints scoped to a specific run."""
    def test_returns_200_or_404(self):
        r = client.get("/api/observability/runs/run-001/traces")
        assert r.status_code in (200, 404)
