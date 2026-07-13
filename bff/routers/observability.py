"""Observability router stub."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/observability/summary")
async def get_summary() -> dict:
    return {"data": {}, "stub": True}


@router.get("/observability/runs")
async def get_obs_runs() -> dict:
    return {"data": [], "stub": True}


@router.get("/observability/errors")
async def get_obs_errors() -> dict:
    return {"data": [], "stub": True}
