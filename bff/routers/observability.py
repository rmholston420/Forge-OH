"""Observability router — Phase 4 stubs for metrics, browser frames, and traces."""
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get("/runs/{run_id}/metrics")
async def get_run_metrics(run_id: str) -> dict:
    return {
        "data": {
            "runId": run_id,
            "tokenCount": 0,
            "toolCallCount": 0,
            "filesTouchedCount": 0,
            "costUsd": 0.0,
            "durationMs": None,
            "series": [],
        }
    }


@router.get("/runs/{run_id}/browser")
async def get_browser_frames(run_id: str) -> dict:
    """Returns browser automation frames. Empty while no BrowserGym session active."""
    return {"data": []}


@router.get("/runs/{run_id}/trace")
async def get_run_trace(run_id: str) -> dict:
    """Returns OpenTelemetry trace. 404 when no trace exists for this run."""
    # Stub: return a minimal single-span trace so the UI is exercised
    now = datetime.now(timezone.utc).isoformat()
    return {
        "data": {
            "traceId": f"trace-{run_id[:8]}",
            "runId": run_id,
            "rootSpan": {
                "spanId": "root-001",
                "traceId": f"trace-{run_id[:8]}",
                "parentSpanId": None,
                "name": "run.execute",
                "status": "ok",
                "startTime": now,
                "endTime": None,
                "durationMs": None,
                "attributes": {"run.id": run_id},
                "events": [],
                "children": [],
            },
            "totalSpans": 1,
            "durationMs": None,
            "startTime": now,
            "endTime": None,
            "hasErrors": False,
        }
    }
