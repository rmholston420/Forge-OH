"""Tests for bff/routers/metrics.py.

Metrics endpoints now aggregate from `/api/conversations/search` via
`bff.services.metrics_aggregation`. Tests patch `_fetch_all_conversations`
so they don't require a live agent-server.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import metrics

app = FastAPI()
app.include_router(metrics.router, prefix="/api")
client = TestClient(app)


def _mk_conv(
    *,
    conv_id: str,
    status: str = "finished",
    cost: float = 0.5,
    tokens: int = 1000,
    model: str = "openai/qwen3.6:35b-a3b",
    workspace_id: str = "colossus-ollama",
    workspace_name: str = "colossus-ollama",
    minutes_ago: int = 60,
    duration_minutes: int = 5,
) -> dict[str, Any]:
    created = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    updated = created + timedelta(minutes=duration_minutes)
    return {
        "id": conv_id,
        "execution_status": status,
        "created_at": created.isoformat(),
        "updated_at": updated.isoformat(),
        "workspace": {"workspace_id": workspace_id, "name": workspace_name},
        "metrics": {
            "model_name": model,
            "accumulated_cost": cost,
            "accumulated_token_usage": {
                "prompt_tokens": tokens // 2,
                "completion_tokens": tokens // 2,
            },
        },
    }


CONVS: list[dict[str, Any]] = [
    _mk_conv(conv_id="c1", status="finished", cost=1.0, tokens=2000, minutes_ago=30),
    _mk_conv(conv_id="c2", status="finished", cost=0.5, tokens=1000, minutes_ago=90),
    _mk_conv(conv_id="c3", status="error", cost=0.25, tokens=500, minutes_ago=180),
    _mk_conv(
        conv_id="c4",
        status="finished",
        cost=2.0,
        tokens=4000,
        minutes_ago=60 * 24 * 10,  # 10 days ago
    ),
]


class TestSummary:
    def test_summary_shape_and_math(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/summary?period=7d")
        assert r.status_code == 200
        body = r.json()
        # 3 rows in 7d window (c4 is 10d ago and excluded)
        assert body["totalRuns"] == 3
        assert body["totalCostUsd"] == 1.75
        assert body["totalTokens"] == 3500
        # 2 finished / (2 finished + 1 error) = 0.6667
        assert abs(body["successRate"] - 2 / 3) < 0.001
        assert abs(body["failureRate"] - 1 / 3) < 0.001
        assert body["deltaRuns"] is not None
        assert body["deltaCostUsd"] is not None

    def test_summary_all_deltas_null(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/summary?period=all")
        assert r.status_code == 200
        body = r.json()
        assert body["totalRuns"] == 4
        assert body["deltaRuns"] is None
        assert body["deltaCostUsd"] is None

    def test_summary_empty(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=[],
        ):
            r = client.get("/api/metrics/summary?period=7d")
        body = r.json()
        assert body["totalRuns"] == 0
        assert body["successRate"] == 0.0
        assert body["failureRate"] == 0.0


class TestDaily:
    def test_daily_length_matches_period(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/daily?period=7d")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 7
        # rows in chronological order
        assert rows[0]["date"] <= rows[-1]["date"]
        for row in rows:
            assert set(row.keys()) == {"date", "runs", "costUsd", "tokens", "successRate"}


class TestModels:
    def test_model_breakdown(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/models?period=all")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        m = rows[0]
        assert m["model"] == "openai/qwen3.6:35b-a3b"
        assert m["runs"] == 4
        assert m["tokens"] == 7500


class TestWorkspaces:
    def test_workspace_breakdown(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/workspaces?period=all")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        w = rows[0]
        assert w["workspaceId"] == "colossus-ollama"
        assert w["runs"] == 4


class TestLegacyEndpoints:
    def test_root_metrics_200(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_run_metrics_stub_200(self) -> None:
        r = client.get("/api/metrics/runs/run-001")
        assert r.status_code == 200

    def test_workspace_metrics_200(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/workspaces/colossus-ollama")
        assert r.status_code == 200
        body = r.json()
        assert body["runs"] == 4

    def test_cost_endpoint_200(self) -> None:
        with patch(
            "bff.services.metrics_aggregation._fetch_all_conversations",
            return_value=CONVS,
        ):
            r = client.get("/api/metrics/cost")
        assert r.status_code == 200
        assert "totalCostUsd" in r.json()
