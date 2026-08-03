"""Trajectory sidecar producer (Slice F.12).

The trajectory STOP hook (``openhands_tools_ext.trajectory.hook``) reads
``$WORKSPACE/.forge-oh/trajectory-sidecar.json`` at STOP time to enrich
the ``RunSummary`` it inserts into ``trajectories.db``. Without a
producer, every trajectory row has an empty ``task_description`` and no
diffs / plan / symptoms / repograph symbols.

This module owns the *BFF-authored* half of that contract:

* :func:`seed_sidecar` — called from :mod:`bff.routers.runs` right after
  the agent-server conversation is created. Writes ``task_description``
  (from the initial user prompt) so the trajectory hook can key runs by
  what the user actually asked for.
* :func:`update_sidecar` — additive helper for future writers (e.g. a
  planner step that fills in ``plan``, or a verify branch that fills in
  ``symptom``) to mutate a specific session slot without stomping the
  other keys.

The sidecar format matches what
:func:`openhands_tools_ext.trajectory.hook._load_sidecar` expects:

    {
      "<session_id>": {
        "task_description": "...",
        "plan": "...",
        "symptom": "...",
        "repograph_repo_key": "...",
        "repograph_symbols": ["a.b", ...],
        "diffs": [{"path": "a.py", "lines_added": 3, ...}]
      }
    }

Design notes:

* Every write is best-effort and *never* raises out of the caller —
  matching how the hook itself treats malformed state. A missing
  workspace directory, a permissions error, or a lock contention should
  not block a run from starting. Failures are logged at WARNING.
* Concurrent writers on the same file are serialized by an
  :class:`fcntl.LOCK_EX` on the sidecar file. This is defensive: we
  expect a single BFF process today, but a future indexer drain or
  planner may append fields on the same session.
* No dependency on the ``openhands_tools_ext`` package: the sidecar file
  layout is the contract, not a Python import boundary.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Kept in sync with openhands_tools_ext.trajectory.hook.
# Duplicated intentionally: the hook lives in the agent-server process
# and importing it from the BFF would drag the whole trajectory package
# (including the SQLite store) into every BFF request path.
_STATE_DIR = ".forge-oh"
_SIDECAR_FILE = "trajectory-sidecar.json"


def sidecar_path(workspace: str | os.PathLike[str]) -> Path:
    """Return the absolute path to the sidecar for a given workspace."""
    return Path(workspace) / _STATE_DIR / _SIDECAR_FILE


def _read_payload_locked(path: Path) -> dict[str, Any]:
    """Read the sidecar JSON *while the caller already holds the flock*.

    Returns ``{}`` on any read/parse error. Callers MUST already hold
    the exclusive flock on the lock file so the read-modify-write cycle
    is a single atomic transaction.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("sidecar %s unreadable, starting fresh: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _rmw(path: Path, mutate: Any) -> None:
    """Read-modify-write the sidecar under an exclusive flock.

    ``mutate`` receives the current payload dict (or ``{}`` if the file
    doesn't exist) and should modify it in place. The whole cycle runs
    under a single flock so concurrent writers cannot lose each other's
    updates. The tmp file is unique per (pid, tid) to avoid rename
    contention across workers.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    tid = threading.get_native_id()
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{tid}.tmp")
    with lock_path.open("a+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            payload = _read_payload_locked(path)
            mutate(payload)
            try:
                with tmp.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2, sort_keys=True)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    tmp.unlink()
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
    # Deliberately NOT unlinking the lock file. Unlinking it breaks the
    # cross-writer mutual-exclusion guarantee: two writers that open the
    # lockfile between an unlink and a re-create bind their flocks to
    # *different inodes* and both proceed to run the RMW cycle in
    # parallel, silently losing updates. The lockfile is small
    # (0 bytes), lives in the workspace's ``.forge-oh`` state dir where
    # it doesn't clutter anything the user sees, and doesn't need
    # per-run cleanup.


def seed_sidecar(
    *,
    workspace: str | os.PathLike[str],
    session_id: str,
    task_description: str,
) -> Path | None:
    """Seed the sidecar for ``session_id`` with the initial task prompt.

    Called from the create-run flow after the agent-server has returned
    a conversation id. Idempotent: if the session slot already exists
    (e.g. a follow-up sidecar writer beat us to it), its existing keys
    are preserved and only missing/empty ``task_description`` is filled.

    Returns the sidecar path on success, ``None`` on any error. Never
    raises.
    """
    if not session_id:
        log.warning("seed_sidecar called without session_id; skipping")
        return None
    try:
        path = sidecar_path(workspace)

        def _mutate(payload: dict[str, Any]) -> None:
            slot = payload.get(session_id)
            if not isinstance(slot, dict):
                slot = {}
            # Preserve any existing task_description written by a
            # downstream producer; only fill when empty.
            if not slot.get("task_description"):
                slot["task_description"] = task_description or ""
            payload[session_id] = slot

        _rmw(path, _mutate)
        return path
    except OSError as exc:
        # EACCES / ENOSPC / ENAMETOOLONG etc.
        log.warning(
            "seed_sidecar: could not write %s for session %s: %s",
            workspace,
            session_id,
            exc,
        )
        return None
    except Exception as exc:  # pragma: no cover — belt & suspenders
        log.warning("seed_sidecar: unexpected error: %s", exc)
        return None


def update_sidecar(
    *,
    workspace: str | os.PathLike[str],
    session_id: str,
    fields: dict[str, Any],
) -> Path | None:
    """Merge ``fields`` into the session's sidecar slot.

    Missing keys are added; existing keys are overwritten. Empty-string
    values in ``fields`` are respected (i.e. an explicit clear is
    honored). Non-serializable values are dropped with a warning.

    Returns the sidecar path on success, ``None`` on any error.
    """
    if not session_id:
        log.warning("update_sidecar called without session_id; skipping")
        return None
    if not fields:
        return None
    try:
        # Validate the update payload is JSON-serializable before we
        # merge — a bad value shouldn't corrupt the whole file.
        try:
            json.dumps(fields)
        except (TypeError, ValueError) as exc:
            log.warning(
                "update_sidecar: dropping non-serializable fields for %s: %s",
                session_id,
                exc,
            )
            return None
        path = sidecar_path(workspace)

        def _mutate(payload: dict[str, Any]) -> None:
            slot = payload.get(session_id)
            if not isinstance(slot, dict):
                slot = {}
            slot.update(fields)
            payload[session_id] = slot

        _rmw(path, _mutate)
        return path
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            log.error("update_sidecar: disk full while writing %s", workspace)
        else:
            log.warning(
                "update_sidecar: could not write for session %s: %s",
                session_id,
                exc,
            )
        return None
    except Exception as exc:  # pragma: no cover
        log.warning("update_sidecar: unexpected error: %s", exc)
        return None
