"""Metrics router — temporary stub for Forge-OH vertical slice.

The original OpenHands metrics router computed summaries/daily/model/workspace
metrics over the runs store. For Forge-OH V1 we collapsed this to a few
zero-valued placeholders to keep UI integration and tests unblocked.

TODO(foh-phase2):
- Reintroduce aggregation over runs once Forge-OH run model is stable
- Restore /summary, /daily, /models, /workspaces or Forge-OH equivalents
- Define a proper metrics contract consumed by the dashboard

"""
from fastapi import APIRouter

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics():
    return {"ok": True, "runs": 0, "costUsd": 0.0}


@router.get("/runs/{run_id}")
def get_run_metrics(run_id: str):
    return {"runId": run_id, "costUsd": 0.0, "tokens": 0}


@router.get("/workspaces/{workspace_id}")
def get_workspace_metrics(workspace_id: str):
    return {"workspaceId": workspace_id, "costUsd": 0.0, "runs": 0}


@router.get("/cost")
def get_cost_summary():
    return {"totalCostUsd": 0.0}
