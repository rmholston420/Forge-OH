"""Shared helper: page through an agent-server conversation's event stream.

Used by:
- bff.routers.runs (plan/commands/artifacts derivations)
- bff.routers.observability (trace/span derivation)
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from bff.openhands_client import get_client


async def fetch_all_events(run_id: str) -> list[dict[str, Any]]:
    """Page through /api/conversations/{run_id}/events/search (limit=100)."""
    client = get_client()
    items: list[dict[str, Any]] = []
    page_id: Optional[str] = None
    # Safety cap on total pages
    for _ in range(200):
        params: dict[str, Any] = {"limit": 100, "sort_order": "TIMESTAMP"}
        if page_id:
            params["page_id"] = page_id
        try:
            resp = await client.get(
                f"/api/conversations/{run_id}/events/search",
                params=params,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="run not found")
        resp.raise_for_status()
        payload = resp.json() or {}
        if isinstance(payload, list):
            items.extend(payload)
            break
        batch = payload.get("items") or payload.get("data") or payload.get("events") or []
        items.extend(batch)
        next_page = payload.get("next_page_id") or payload.get("nextPageId")
        if not next_page or not batch:
            break
        page_id = next_page
    return items
