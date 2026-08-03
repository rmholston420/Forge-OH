"""
In-memory registry mapping ``repo_key`` -> absolute workspace path.

Populated by ``POST /api/repograph/index`` so subsequent RepoGraph endpoints
(``co_changed`` in particular) can locate the on-disk repo to shell out to
``git log``. If the BFF process restarts the registry is empty; the caller
re-indexes to repopulate. That's an acceptable trade-off for single-user
local-first; adding SQLite persistence is a straightforward follow-up if
we want durability.

Thread-safe (uses a module-level lock) so concurrent requests to
``/index`` and read endpoints don't race.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceEntry:
    repo_key: str
    absolute_path: str


_registry: dict[str, WorkspaceEntry] = {}
_lock = threading.Lock()


def register(repo_key: str, absolute_path: str | Path) -> WorkspaceEntry:
    """Record (or update) the mapping from repo_key to absolute workspace path."""
    resolved = str(Path(absolute_path).resolve())
    entry = WorkspaceEntry(repo_key=repo_key, absolute_path=resolved)
    with _lock:
        _registry[repo_key] = entry
    return entry


def lookup(repo_key: str) -> WorkspaceEntry | None:
    with _lock:
        return _registry.get(repo_key)


def list_entries() -> list[WorkspaceEntry]:
    with _lock:
        return list(_registry.values())


def clear() -> None:
    """Test helper — never call from production code paths."""
    with _lock:
        _registry.clear()
