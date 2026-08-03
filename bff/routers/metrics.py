"""Metrics router — serves the shape the frontend Metrics dashboard expects.

The frontend (src/features/metrics/schemas.ts) expects:
  GET /api/metrics/summary?period=…    → RunMetricsSummary
  GET /api/metrics/daily?period=…      → DailyMetricsPoint[]
  GET /api/metrics/models?period=…     → ModelBreakdown[]
  GET /api/metrics/workspaces?period=… → WorkspaceBreakdown[]

Legacy per-entity endpoints preserved for compat:
  GET /api/metrics                       → global summary (short)
  GET /api/metrics/runs/{run_id}         → per-run
  GET /api/metrics/workspaces/{ws_id}    → per-workspace
  GET /api/metrics/cost                  → total cost

Current implementation returns zero-value placeholders in the correct
shape so the dashboard renders instead of 404-ing. TODO(foh-metrics-agg):
compute real aggregates from /api/conversations/search once the run
model stabilizes (see BUILD_LOG Task 4.x).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query

router = APIRouter(prefix="/metrics", tags=["metrics"])

Period = Literal["7d", "30d", "90d", "all"]


# ---------------------------------------------------------------------------
# Frontend-contract endpoints (new)
# ---------------------------------------------------------------------------


@router.get("/summary")
def get_metrics_summary(period: Period = Query("7d")) -> dict:
    """RunMetricsSummary shape — see src/features/metrics/schemas.ts."""
    return {
        "totalRuns": 0,
        "totalCostUsd": 0.0,
        "totalTokens": 0,
        "avgDurationMs": 0.0,
        "successRate": 0.0,
        "failureRate": 0.0,
        "p50DurationMs": 0.0,
        "p95DurationMs": 0.0,
        "deltaRuns": None if period == "all" else 0,
        "deltaCostUsd": None if period == "all" else 0.0,
    }


@router.get("/daily")
def get_daily_metrics(period: Period = Query("7d")) -> list[dict]:
    """DailyMetricsPoint[] — one row per day in the period."""
    days = {"7d": 7, "30d": 30, "90d": 90, "all": 30}[period]
    today = datetime.now(UTC).date()
    return [
        {
            "date": (today - timedelta(days=i)).isoformat(),
            "runs": 0,
            "costUsd": 0.0,
            "tokens": 0,
            "successRate": 0.0,
        }
        for i in range(days - 1, -1, -1)
    ]


@router.get("/models")
def get_model_breakdown(period: Period = Query("7d")) -> list[dict]:  # noqa: ARG001
    """ModelBreakdown[] — one row per LLM model used in the period."""
    return []


@router.get("/workspaces")
def get_workspace_breakdown(period: Period = Query("7d")) -> list[dict]:  # noqa: ARG001
    """WorkspaceBreakdown[] — one row per workspace with runs in the period."""
    return []


# ---------------------------------------------------------------------------
# Legacy per-entity endpoints (kept for compat with any lingering callers)
# ---------------------------------------------------------------------------


@router.get("")
def get_metrics() -> dict:
    return {"ok": True, "runs": 0, "costUsd": 0.0}


@router.get("/runs/{run_id}")
def get_run_metrics(run_id: str) -> dict:
    return {"runId": run_id, "costUsd": 0.0, "tokens": 0}


@router.get("/workspaces/{workspace_id}")
def get_workspace_metrics(workspace_id: str) -> dict:
    return {"workspaceId": workspace_id, "costUsd": 0.0, "runs": 0}


@router.get("/cost")
def get_cost_summary() -> dict:
    return {"totalCostUsd": 0.0}
