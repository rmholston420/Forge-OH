"""``/api/selfeval`` — GUI surface for the on-demand self-eval harness.

Endpoints:

- ``GET  /api/selfeval/cycles``               — list every cycle summary on disk.
- ``GET  /api/selfeval/cycles/{filename}``    — full summary JSON for one cycle.
- ``GET  /api/selfeval/proposals``            — list every proposal file on disk.
- ``GET  /api/selfeval/proposals/{filename}`` — raw Markdown body for one proposal.
- ``POST /api/selfeval/run``                  — launch a cycle via
  ``systemctl --user start forge-oh-selfeval.service``.
- ``GET  /api/selfeval/status``               — current cycle in-flight state.

Filenames are validated against a strict regex and their fully-resolved path
must remain inside the configured summary/proposal directory. Path-traversal
attempts return 400.

See ADR-011 for the launch model (on-demand only, no ``.timer``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/selfeval", tags=["selfeval"])


# ---------------------------------------------------------------------------
# Configuration \u2014 mirror the CLI defaults so both surfaces read/write the
# same files. Env overrides are the escape hatch when someone reorganizes.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUMMARY_DIR = (
    Path(os.environ.get("FORGE_SELFEVAL_SUMMARY_DIR", _REPO_ROOT / "docs" / "selfeval"))
    .expanduser()
    .resolve()
)
_PROPOSAL_DIR = (
    Path(os.environ.get("FORGE_SELFEVAL_PROPOSAL_DIR", _REPO_ROOT / "docs" / "proposals"))
    .expanduser()
    .resolve()
)
_SERVICE_UNIT = os.environ.get(
    "FORGE_SELFEVAL_SERVICE_UNIT", "forge-oh-selfeval.service"
)

# Filename shapes we accept:
# - summary:  2026-08-03-selfeval.json  or  2026-08-03-selfeval-2230.json
# - proposal: 2026-08-03-<task_id>-<run_short>.md  (+ optional -vN)
_SUMMARY_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-selfeval(?:-\d{4})?\.json$")
_PROPOSAL_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9\-]+\.md$")


def _safe_child(name: str, root: Path, pattern: re.Pattern[str]) -> Path:
    """Return ``root / name`` iff (a) ``name`` matches ``pattern`` AND
    (b) the fully-resolved path is a child of ``root``. Otherwise raises
    HTTPException(400). This is the ONLY place path traversal is guarded
    in this router; every filename param must go through it."""
    if not pattern.match(name):
        raise HTTPException(status_code=400, detail=f"invalid filename: {name!r}")
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path traversal blocked") from exc
    return candidate


# ---------------------------------------------------------------------------
# In-process cycle-lock state.
# ---------------------------------------------------------------------------


class _CycleState:
    """Tracks whether a self-eval cycle is currently in flight in this BFF."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.running: bool = False
        self.started_at: str | None = None
        self.last_result: dict[str, Any] | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at,
            "last_result": self.last_result,
        }


_state = _CycleState()


class RunResponse(BaseModel):
    """POST /run response body."""

    started_at: str
    service_unit: str
    already_running: bool = False


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------


@router.get("/cycles")
def list_cycles() -> dict[str, Any]:
    """List every cycle summary on disk (newest first), lightweight shape.

    Never fails on a missing directory \u2014 an empty install returns ``[]``.
    """
    items: list[dict[str, Any]] = []
    if _SUMMARY_DIR.is_dir():
        for p in sorted(_SUMMARY_DIR.iterdir(), reverse=True):
            if not p.is_file() or not _SUMMARY_NAME_RE.match(p.name):
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("selfeval: skipping unreadable %s: %s", p.name, exc)
                continue
            items.append(
                {
                    "filename": p.name,
                    "started_at": data.get("started_at"),
                    "finished_at": data.get("finished_at"),
                    "manifest_path": data.get("manifest_path"),
                    "selection_strategy": data.get("selection_strategy"),
                    "tasks_selected": data.get("tasks_selected", 0),
                    "tasks_passed": data.get("tasks_passed", 0),
                    "tasks_failed": data.get("tasks_failed", 0),
                    "tasks_timed_out": data.get("tasks_timed_out", 0),
                    "tasks_errored": data.get("tasks_errored", 0),
                }
            )
    return {"cycles": items}


@router.get("/cycles/{filename}")
def get_cycle(filename: str) -> dict[str, Any]:
    """Return the full summary JSON for one cycle."""
    path = _safe_child(filename, _SUMMARY_DIR, _SUMMARY_NAME_RE)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"cycle not found: {filename}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"cycle unreadable: {exc}") from exc


@router.get("/proposals")
def list_proposals(date: str | None = None) -> dict[str, Any]:
    """List every proposal Markdown on disk. Optionally filter by ``date=YYYY-MM-DD``."""
    if date is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    items: list[dict[str, Any]] = []
    if _PROPOSAL_DIR.is_dir():
        for p in sorted(_PROPOSAL_DIR.iterdir(), reverse=True):
            if not p.is_file() or not _PROPOSAL_NAME_RE.match(p.name):
                continue
            if date and not p.name.startswith(date):
                continue
            items.append(
                {
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        p.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    return {"proposals": items}


@router.get("/proposals/{filename}")
def get_proposal(filename: str) -> dict[str, Any]:
    """Return the raw Markdown body of one proposal."""
    path = _safe_child(filename, _PROPOSAL_DIR, _PROPOSAL_NAME_RE)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"proposal not found: {filename}")
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"proposal unreadable: {exc}") from exc
    return {"filename": filename, "body": body}


@router.get("/status")
def get_status() -> dict[str, Any]:
    """Current cycle in-flight state. Cheap; safe to poll from the frontend."""
    return _state.snapshot()


@router.post("/run", response_model=RunResponse)
async def post_run() -> RunResponse:
    """Launch a self-eval cycle via ``systemctl --user start`` (fire-and-forget).

    Returns 409 if a cycle is already in flight in this BFF process. The
    ``systemctl start`` call itself blocks only until the service transitions
    to ``activating``; the actual harness runs to completion in the background.
    Cycle-complete state is picked up on the next ``GET /status`` from
    reading the unit's ``ActiveState`` (see :func:`_reap_cycle`).
    """
    if _state.running:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "self-eval cycle already running",
                "state": _state.snapshot(),
            },
        )

    async with _state._lock:
        # Re-check under lock (double-check to avoid TOCTOU).
        if _state.running:
            raise HTTPException(status_code=409, detail="self-eval cycle already running")
        started_at = datetime.now(timezone.utc).isoformat()
        _state.running = True
        _state.started_at = started_at
        _state.last_result = None

    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "start",
            "--no-block",
            _SERVICE_UNIT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            _state.running = False
            _state.last_result = {
                "ok": False,
                "returncode": proc.returncode,
                "stderr": stderr.decode(errors="replace")[-500:],
            }
            raise HTTPException(
                status_code=502,
                detail=f"systemctl start failed (rc={proc.returncode}): "
                f"{stderr.decode(errors='replace')[-200:]}",
            )
    except FileNotFoundError:
        _state.running = False
        raise HTTPException(
            status_code=500,
            detail="systemctl not on PATH \u2014 self-eval requires user-scoped systemd",
        ) from None

    # Spawn a reaper task so the state clears when the unit finishes.
    asyncio.create_task(_reap_cycle())
    return RunResponse(started_at=started_at, service_unit=_SERVICE_UNIT)


async def _reap_cycle(*, poll_interval_sec: float = 5.0) -> None:
    """Poll ``systemctl --user is-active`` until the service leaves activating/active
    and record the final ActiveState in ``_state.last_result``. Best-effort."""
    try:
        # Give the unit a moment to transition into activating.
        await asyncio.sleep(1.0)
        while True:
            proc = await asyncio.create_subprocess_exec(
                "systemctl",
                "--user",
                "is-active",
                _SERVICE_UNIT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            active = stdout.decode(errors="replace").strip()
            if active not in ("active", "activating", "reloading"):
                _state.last_result = {
                    "ok": active in ("inactive", "deactivating"),
                    "active_state": active,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
                _state.running = False
                return
            await asyncio.sleep(poll_interval_sec)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("selfeval reaper failed: %s", exc)
        _state.running = False
        _state.last_result = {"ok": False, "error": str(exc)}
