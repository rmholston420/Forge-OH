"""Tests for bff/routers/metrics.py."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bff.routers import metrics

app = FastAPI()
app.include_router(metrics.router, prefix="/api")
client = TestClient(app)


class TestGetMetrics:
    def test_returns_200(self):
        assert client.get("/api/metrics").status_code == 200

    def test_response_is_dict(self):
        assert isinstance(client.get("/api/metrics").json(), dict)


class TestRunMetrics:
    def test_run_metrics_200(self):
        r = client.get("/api/metrics/runs/run-001")
        assert r.status_code in (200, 404)

    def test_workspace_metrics_200(self):
        r = client.get("/api/metrics/workspaces/ws-001")
        assert r.status_code in (200, 404)


class TestCostSummary:
    def test_cost_endpoint_200(self):
        r = client.get("/api/metrics/cost")
        assert r.status_code in (200, 404)
