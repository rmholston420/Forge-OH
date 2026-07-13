"""Observability router — temporary trace stubs for Forge-OH.

Originally this router exposed run-level metrics, browser frames, and traces.
For the Forge-OH vertical slice it has been narrowed to empty trace/span
collections to exercise the frontend without committing to a final schema.

TODO(foh-phase2):
- Define Forge-OH observability story (traces, metrics, logs)
- Restore or redesign run-level endpoints expected by the UI
- Integrate with real tracing/metrics backends once chosen

"""
from fastapi import APIRouter

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces")
def list_traces():
    return {"data": []}


@router.get("/traces/{trace_id}")
def get_trace(trace_id: str):
    return {"traceId": trace_id, "spans": []}


@router.get("/traces/{trace_id}/spans")
def list_spans(trace_id: str):
    return {"data": []}


@router.get("/runs/{run_id}/traces")
def list_run_traces(run_id: str):
    return {"data": []}
