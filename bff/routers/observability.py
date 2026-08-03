"""Observability router — real traces derived from the event stream.

Slice 7F (Option A): reconstruct spans on demand from agent-server events.
No persistent SQLite store, no background subscriber; single-user local-first.

Contract (frontend consumers under /observability):
  GET /observability/runs/{run_id}/traces      → {data: [TraceSummary]}
  GET /observability/traces/{trace_id}         → {data: TraceSummary, spans}
  GET /observability/traces/{trace_id}/spans   → {data: [TraceSpan]}
  GET /observability/traces                    → {data: []}   (list-all unsupported;
                                                  aggregate discovery lives at
                                                  /api/runs listing.)

trace_id == run_id == conversation UUID. Each conversation is one trace.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from bff.services.event_fetch import fetch_all_events
from bff.services.trace_reconstruction import build_spans, build_trace_summary

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces")
async def list_all_traces() -> dict[str, Any]:
    """Not supported: traces are always scoped to a run.

    Frontend should call /observability/runs/{run_id}/traces or list runs
    via /api/runs and fetch each trace by id.
    """
    return {"data": []}


@router.get("/runs/{run_id}/traces")
async def list_run_traces(run_id: str) -> dict[str, Any]:
    events = await fetch_all_events(run_id)
    spans = build_spans(events, run_id)
    summary = build_trace_summary(spans, run_id)
    # One trace per conversation; return as a list for uniformity.
    return {"data": [summary]}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    events = await fetch_all_events(trace_id)
    spans = build_spans(events, trace_id)
    summary = build_trace_summary(spans, trace_id)
    return {"data": {**summary, "spans": spans}}


@router.get("/traces/{trace_id}/spans")
async def list_spans(trace_id: str) -> dict[str, Any]:
    events = await fetch_all_events(trace_id)
    spans = build_spans(events, trace_id)
    return {"data": spans}
