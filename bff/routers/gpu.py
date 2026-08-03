"""GPU thermal monitor routes (Slice F.16).

Read-only endpoints backed by the singleton in
:mod:`bff.services.gpu_monitor`. There is no configuration surface:
the poller starts in the BFF lifespan and these routes just observe
its ring buffer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from bff.services import gpu_monitor

router = APIRouter(prefix="/api/gpu", tags=["gpu"])


@router.get("")
def gpu_snapshot() -> dict[str, Any]:
    """Latest sample per GPU + advisory cutoff.

    Returns ``available=false`` with an ``unavailable`` payload when
    ``nvidia-smi`` isn't reachable — the frontend uses that to hide
    the sparkline gracefully instead of erroring.
    """
    return gpu_monitor.get_monitor().snapshot()


@router.get("/history")
def gpu_history(
    window_sec: float | None = Query(
        default=None,
        ge=0,
        description=(
            "Time window in seconds. Omit to get the entire ring "
            "(bounded by FORGE_GPU_HISTORY_SEC, default 900 s)."
        ),
    ),
) -> dict[str, Any]:
    """Ring slice, keyed by GPU index (string, to survive JSON)."""
    return gpu_monitor.get_monitor().history(window_sec)
