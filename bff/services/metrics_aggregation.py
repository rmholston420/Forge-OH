"""
bff/services/metrics_aggregation.py

Aggregate conversation-level data from the OpenHands agent-server
(`/api/conversations/search`) into the shapes the frontend metrics
dashboard expects:

  - RunMetricsSummary   (bff/routers/metrics.py::get_metrics_summary)
  - DailyMetricsPoint[] (bff/routers/metrics.py::get_daily_metrics)
  - ModelBreakdown[]    (bff/routers/metrics.py::get_model_breakdown)
  - WorkspaceBreakdown[] (bff/routers/metrics.py::get_workspace_breakdown)

Design goals (local-first, single-user Colossus):
  - Fetch every conversation up to a hard cap (default 2000). For a local
    workstation this is well under a second.
  - Compute deterministic aggregates. No caching yet — the frontend has
    react-query staleTime; the BFF stays stateless.
  - Successful runs are `execution_status == "finished"`; failed runs are
    `execution_status == "error"`. Anything else (idle/running/paused/...)
    is excluded from success/failure denominators to avoid biasing the
    rate while a run is mid-flight.
  - Duration = updated_at - created_at (ms). Includes in-flight runs so
    the number reflects observed reality, not a snapshot pruning artefact.

Anything that isn't computable from the ConversationInfo/MetricsSnapshot
schema stays at a safe default (0 / null) instead of guessing.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from bff.openhands_client import get_client

logger = logging.getLogger(__name__)

Period = Literal["7d", "30d", "90d", "all"]

_PERIOD_DAYS: dict[Period, int | None] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}

# Hard cap so a runaway agent-server can't hang the dashboard.
_MAX_CONVERSATIONS = 2000
_PAGE_LIMIT = 100


async def _fetch_all_conversations() -> list[dict[str, Any]]:
    """Fetch every ConversationInfo, paginated. Capped at _MAX_CONVERSATIONS."""
    client = get_client()
    out: list[dict[str, Any]] = []
    page_id: str | None = None

    for _ in range((_MAX_CONVERSATIONS // _PAGE_LIMIT) + 1):
        params: dict[str, Any] = {"limit": _PAGE_LIMIT}
        if page_id:
            params["page_id"] = page_id
        try:
            resp = await client.get("/api/conversations/search", params=params)
        except Exception as exc:  # network, connection, etc.
            logger.warning("metrics_aggregation: fetch failed: %s", exc)
            return out
        if resp.status_code != 200:
            logger.warning(
                "metrics_aggregation: /api/conversations/search returned %s",
                resp.status_code,
            )
            return out
        page = resp.json()
        items = page.get("items", []) or []
        out.extend(items)
        page_id = page.get("next_page_id")
        if not page_id or len(out) >= _MAX_CONVERSATIONS:
            break
    return out[:_MAX_CONVERSATIONS]


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        # fromisoformat accepts trailing 'Z' from py3.11+; be defensive anyway
        s = value.rstrip("Z")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _within_period(created: datetime | None, period: Period) -> bool:
    if created is None:
        return period == "all"
    days = _PERIOD_DAYS[period]
    if days is None:
        return True
    cutoff = datetime.now(UTC) - timedelta(days=days)
    return created >= cutoff


def _prior_window(period: Period) -> tuple[datetime, datetime] | None:
    """Return the (start, end) of the immediately-preceding equal-length window.
    Returns None for period='all' (deltas are not defined there)."""
    days = _PERIOD_DAYS[period]
    if days is None:
        return None
    now = datetime.now(UTC)
    curr_start = now - timedelta(days=days)
    prev_start = curr_start - timedelta(days=days)
    return prev_start, curr_start


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    # Linear interpolation between closest ranks (numpy-free).
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _extract_row(conv: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw ConversationInfo into the fields we aggregate on.

    Model resolution order (most reliable first):
      1. `metrics.model_name`  — populated after the LLM has actually run
      2. `agent.llm.model`     — populated at conversation creation time
      3. fallback: "unknown"

    Workspace resolution:
      LocalWorkspace exposes `working_dir` + `kind`. Older/other workspace
      variants may expose `workspace_id`, `path`, or `name` — we accept any
      of those, but prefer `working_dir` because that's what the current
      upstream schema documents.
    """
    metrics = conv.get("metrics") or {}
    token_usage = metrics.get("accumulated_token_usage") or {}

    prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(token_usage.get("completion_tokens", 0) or 0)
    tokens = prompt_tokens + completion_tokens
    # Fallback to `total_tokens` if the split fields aren't present
    if tokens == 0:
        tokens = int(token_usage.get("total_tokens", 0) or 0)

    created = _parse_dt(conv.get("created_at"))
    updated = _parse_dt(conv.get("updated_at"))
    duration_ms = 0.0
    if created and updated and updated >= created:
        duration_ms = (updated - created).total_seconds() * 1000.0

    # --- Model ---
    model_name = metrics.get("model_name") or ""
    if not model_name:
        agent = conv.get("agent") or {}
        llm = agent.get("llm") or {}
        model_name = llm.get("model") or ""
    if not model_name:
        model_name = "unknown"

    # --- Workspace ---
    workspace = conv.get("workspace") or {}
    workspace_id = (
        workspace.get("working_dir")
        or workspace.get("workspace_id")
        or workspace.get("id")
        or workspace.get("path")
        or "unknown"
    )
    workspace_name = (
        workspace.get("name")
        or workspace.get("working_dir")
        or workspace.get("path")
        or workspace_id
    )

    return {
        "id": conv.get("id") or "",
        "status": conv.get("execution_status") or "",
        "cost_usd": float(metrics.get("accumulated_cost", 0.0) or 0.0),
        "tokens": tokens,
        "model": model_name,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "created_at": created,
        "duration_ms": duration_ms,
    }


def _filter(rows: list[dict[str, Any]], period: Period) -> list[dict[str, Any]]:
    return [r for r in rows if _within_period(r["created_at"], period)]


# ---------------------------------------------------------------------------
# Public: aggregation entry points
# ---------------------------------------------------------------------------


async def summary(period: Period) -> dict[str, Any]:
    convs = await _fetch_all_conversations()
    rows_all = [_extract_row(c) for c in convs]
    rows = _filter(rows_all, period)

    total_runs = len(rows)
    total_cost = sum(r["cost_usd"] for r in rows)
    total_tokens = sum(r["tokens"] for r in rows)

    finished = sum(1 for r in rows if r["status"] == "finished")
    errored = sum(1 for r in rows if r["status"] == "error")
    denom = finished + errored
    success_rate = (finished / denom) if denom else 0.0
    failure_rate = (errored / denom) if denom else 0.0

    durations = [r["duration_ms"] for r in rows if r["duration_ms"] > 0]
    avg_dur = (sum(durations) / len(durations)) if durations else 0.0
    p50 = _percentile(durations, 0.5)
    p95 = _percentile(durations, 0.95)

    # Deltas
    delta_runs: int | None
    delta_cost: float | None
    prior = _prior_window(period)
    if prior is None:
        delta_runs = None
        delta_cost = None
    else:
        prev_start, prev_end = prior
        prior_rows = [
            r
            for r in rows_all
            if r["created_at"] is not None and prev_start <= r["created_at"] < prev_end
        ]
        prior_runs = len(prior_rows)
        prior_cost = sum(r["cost_usd"] for r in prior_rows)
        delta_runs = total_runs - prior_runs
        delta_cost = total_cost - prior_cost

    return {
        "totalRuns": total_runs,
        "totalCostUsd": round(total_cost, 6),
        "totalTokens": total_tokens,
        "avgDurationMs": round(avg_dur, 3),
        "successRate": round(success_rate, 4),
        "failureRate": round(failure_rate, 4),
        "p50DurationMs": round(p50, 3),
        "p95DurationMs": round(p95, 3),
        "deltaRuns": delta_runs,
        "deltaCostUsd": round(delta_cost, 6) if delta_cost is not None else None,
    }


async def daily(period: Period) -> list[dict[str, Any]]:
    convs = await _fetch_all_conversations()
    rows = _filter([_extract_row(c) for c in convs], period)

    days_span = _PERIOD_DAYS[period] or 30
    today = datetime.now(UTC).date()
    # Include today plus (days_span-1) prior days so the range matches
    # _within_period(period)'s cutoff (now - timedelta(days=days_span)).
    buckets: dict[date, dict[str, float]] = {
        (today - timedelta(days=i)): {"runs": 0, "cost": 0.0, "tokens": 0, "fin": 0, "err": 0}
        for i in range(days_span)
    }

    for r in rows:
        c = r["created_at"]
        if c is None:
            continue
        d = c.date()
        b = buckets.get(d)
        if b is None:
            # Row is within the rolling-hour period but bucketing by date
            # can drop the tail day. Skip silently — daily is a chart hint,
            # summary uses row-level totals.
            continue
        b["runs"] += 1
        b["cost"] += r["cost_usd"]
        b["tokens"] += r["tokens"]
        if r["status"] == "finished":
            b["fin"] += 1
        elif r["status"] == "error":
            b["err"] += 1

    out: list[dict[str, Any]] = []
    for d in sorted(buckets.keys()):
        b = buckets[d]
        denom = b["fin"] + b["err"]
        out.append(
            {
                "date": d.isoformat(),
                "runs": int(b["runs"]),
                "costUsd": round(b["cost"], 6),
                "tokens": int(b["tokens"]),
                "successRate": round(b["fin"] / denom, 4) if denom else 0.0,
            }
        )
    return out


async def models(period: Period) -> list[dict[str, Any]]:
    convs = await _fetch_all_conversations()
    rows = _filter([_extract_row(c) for c in convs], period)

    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "cost": 0.0, "tokens": 0, "durations": []}
    )
    for r in rows:
        a = agg[r["model"]]
        a["runs"] += 1
        a["cost"] += r["cost_usd"]
        a["tokens"] += r["tokens"]
        if r["duration_ms"] > 0:
            a["durations"].append(r["duration_ms"])

    out: list[dict[str, Any]] = []
    for model_name, a in sorted(agg.items(), key=lambda kv: kv[1]["runs"], reverse=True):
        durations = a["durations"]
        avg = (sum(durations) / len(durations)) if durations else 0.0
        out.append(
            {
                "model": model_name,
                "runs": int(a["runs"]),
                "costUsd": round(a["cost"], 6),
                "tokens": int(a["tokens"]),
                "avgDurationMs": round(avg, 3),
            }
        )
    return out


async def workspaces(period: Period) -> list[dict[str, Any]]:
    convs = await _fetch_all_conversations()
    rows = _filter([_extract_row(c) for c in convs], period)

    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"name": "", "runs": 0, "cost": 0.0})
    for r in rows:
        a = agg[r["workspace_id"]]
        a["name"] = r["workspace_name"]
        a["runs"] += 1
        a["cost"] += r["cost_usd"]

    out: list[dict[str, Any]] = []
    for ws_id, a in sorted(agg.items(), key=lambda kv: kv[1]["runs"], reverse=True):
        out.append(
            {
                "workspaceId": ws_id,
                "name": a["name"] or ws_id,
                "runs": int(a["runs"]),
                "costUsd": round(a["cost"], 6),
            }
        )
    return out
