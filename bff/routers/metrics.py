"""Metrics router — serves the shape the frontend Metrics dashboard expects.

The frontend (src/features/metrics/schemas.ts) expects:
  GET /api/metrics/summary?period=…    → RunMetricsSummary
  GET /api/metrics/daily?period=…      → DailyMetricsPoint[]
  GET /api/metrics/models?period=…     → ModelBreakdown[]
  GET /api/metrics/workspaces?period=… → WorkspaceBreakdown[]

Aggregates are computed from `/api/conversations/search` (upstream) by
`bff.services.metrics_aggregation`. See that module for methodology.

Legacy per-entity endpoints preserved for compat:
  GET /api/metrics                       → global summary (short)
  GET /api/metrics/runs/{run_id}         → per-run
  GET /api/metrics/workspaces/{ws_id}    → per-workspace
  GET /api/metrics/cost                  → total cost
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from bff.services import metrics_aggregation

router = APIRouter(prefix="/metrics", tags=["metrics"])

Period = Literal["7d", "30d", "90d", "all"]

# Module-level singleton to satisfy ruff B008 (no function call in default args).
_PERIOD_QUERY = Query("7d")


# ---------------------------------------------------------------------------
# Frontend-contract endpoints (real aggregation from agent-server)
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_metrics_summary(period: Period = _PERIOD_QUERY) -> dict:
    """RunMetricsSummary shape — see src/features/metrics/schemas.ts."""
    return await metrics_aggregation.summary(period)


@router.get("/daily")
async def get_daily_metrics(period: Period = _PERIOD_QUERY) -> list[dict]:
    """DailyMetricsPoint[] — one row per day in the period."""
    return await metrics_aggregation.daily(period)


@router.get("/models")
async def get_model_breakdown(period: Period = _PERIOD_QUERY) -> list[dict]:
    """ModelBreakdown[] — one row per LLM model used in the period."""
    return await metrics_aggregation.models(period)


@router.get("/workspaces")
async def get_workspace_breakdown(period: Period = _PERIOD_QUERY) -> list[dict]:
    """WorkspaceBreakdown[] — one row per workspace with runs in the period."""
    return await metrics_aggregation.workspaces(period)


# ---------------------------------------------------------------------------
# Legacy per-entity endpoints (kept for compat with any lingering callers)
# ---------------------------------------------------------------------------


@router.get("")
async def get_metrics() -> dict:
    s = await metrics_aggregation.summary("7d")
    return {"ok": True, "runs": s["totalRuns"], "costUsd": s["totalCostUsd"]}


@router.get("/runs/{run_id}")
def get_run_metrics(run_id: str) -> dict:
    # Per-run metrics are served by /api/runs/{run_id}/metrics (see runs.py).
    # This legacy endpoint returns a small stub so old clients don't 404.
    return {"runId": run_id, "costUsd": 0.0, "tokens": 0}


@router.get("/workspaces/{workspace_id}")
async def get_workspace_metrics(workspace_id: str) -> dict:
    wss = await metrics_aggregation.workspaces("all")
    for ws in wss:
        if ws["workspaceId"] == workspace_id:
            return {
                "workspaceId": workspace_id,
                "costUsd": ws["costUsd"],
                "runs": ws["runs"],
            }
    return {"workspaceId": workspace_id, "costUsd": 0.0, "runs": 0}


@router.get("/cost")
async def get_cost_summary() -> dict:
    s = await metrics_aggregation.summary("all")
    return {"totalCostUsd": s["totalCostUsd"]}
