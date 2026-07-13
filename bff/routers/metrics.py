from fastapi import APIRouter, Query
from datetime import datetime, timezone, timedelta
from typing import Optional
from bff.routers.runs import _RUNS  # reuse existing runs store

router = APIRouter(prefix='/metrics', tags=['metrics'])

def _now(): return datetime.now(timezone.utc)

def _cutoff(period: str) -> Optional[datetime]:
    if period == '7d':  return _now() - timedelta(days=7)
    if period == '30d': return _now() - timedelta(days=30)
    if period == '90d': return _now() - timedelta(days=90)
    return None

def _filter_runs(period: str):
    cut = _cutoff(period)
    runs = list(_RUNS.values())
    if cut:
        runs = [r for r in runs if datetime.fromisoformat(r.createdAt) >= cut]
    return runs

@router.get('/summary')
def get_summary(period: str = Query('30d')):
    runs = _filter_runs(period)
    total = len(runs)
    if total == 0:
        return dict(totalRuns=0, totalCostUsd=0, totalTokens=0, avgDurationMs=0,
                    successRate=0, failureRate=0, p50DurationMs=0, p95DurationMs=0,
                    deltaRuns=None, deltaCostUsd=None)
    costs     = [getattr(r, 'costUsd', 0.0) or 0.0 for r in runs]
    tokens    = [getattr(r, 'tokenCount', 0) or 0 for r in runs]
    durations = [getattr(r, 'durationMs', 0) or 0 for r in runs]
    successes = sum(1 for r in runs if r.status == 'completed')
    durations_sorted = sorted(durations)
    p50 = durations_sorted[len(durations_sorted)//2] if durations_sorted else 0
    p95 = durations_sorted[int(len(durations_sorted)*0.95)] if durations_sorted else 0
    return dict(
        totalRuns=total, totalCostUsd=round(sum(costs), 4),
        totalTokens=sum(tokens),
        avgDurationMs=round(sum(durations)/total, 0) if total else 0,
        successRate=round(successes/total, 4),
        failureRate=round((total-successes)/total, 4),
        p50DurationMs=p50, p95DurationMs=p95,
        deltaRuns=None, deltaCostUsd=None,
    )

@router.get('/daily')
def get_daily(period: str = Query('30d')):
    runs  = _filter_runs(period)
    by_date: dict[str, list] = {}
    for r in runs:
        d = r.createdAt[:10]
        by_date.setdefault(d, []).append(r)
    result = []
    for date, day_runs in sorted(by_date.items()):
        successes = sum(1 for r in day_runs if r.status == 'completed')
        result.append(dict(
            date=date, runs=len(day_runs),
            costUsd=round(sum(getattr(r,'costUsd',0) or 0 for r in day_runs), 4),
            tokens=sum(getattr(r,'tokenCount',0) or 0 for r in day_runs),
            successRate=round(successes/len(day_runs), 4),
        ))
    return result

@router.get('/models')
def get_models(period: str = Query('30d')):
    runs = _filter_runs(period)
    by_model: dict[str, list] = {}
    for r in runs:
        m = getattr(r, 'model', 'unknown') or 'unknown'
        by_model.setdefault(m, []).append(r)
    return [dict(
        model=m,
        runs=len(mrs),
        costUsd=round(sum(getattr(r,'costUsd',0) or 0 for r in mrs), 4),
        tokens=sum(getattr(r,'tokenCount',0) or 0 for r in mrs),
        avgDurationMs=round(sum(getattr(r,'durationMs',0) or 0 for r in mrs)/len(mrs), 0),
    ) for m, mrs in by_model.items()]

@router.get('/workspaces')
def get_workspaces(period: str = Query('30d')):
    runs = _filter_runs(period)
    by_ws: dict[str, list] = {}
    for r in runs:
        ws = getattr(r, 'workspaceId', 'default') or 'default'
        by_ws.setdefault(ws, []).append(r)
    return [dict(
        workspaceId=ws,
        name=ws,
        runs=len(wrs),
        costUsd=round(sum(getattr(r,'costUsd',0) or 0 for r in wrs), 4),
    ) for ws, wrs in by_ws.items()]
