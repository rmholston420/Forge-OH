"""Dependency-injection helper for the shared TrajectoryStore.

FastAPI routers depend on ``get_trajectory_store()``; tests override it
via ``app.dependency_overrides`` to swap in a per-test store rooted at
a ``tmp_path``.

Process-wide singleton so the writer (invoked from a run-completion
hook subprocess) and the router (long-lived) don't fight over the same
SQLite handle from different files. The store is thread-safe for the
router's needs (WAL journal + 5 s busy timeout).
"""

from __future__ import annotations

from openhands_tools_ext.trajectory.store import TrajectoryStore

_STORE: TrajectoryStore | None = None


def get_trajectory_store() -> TrajectoryStore:
    """Return the process-wide TrajectoryStore singleton (lazy)."""
    global _STORE
    if _STORE is None:
        _STORE = TrajectoryStore()
    return _STORE


def reset_trajectory_store() -> None:
    """Reset the singleton — test-only escape hatch."""
    global _STORE
    _STORE = None
