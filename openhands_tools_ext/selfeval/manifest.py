"""Manifest loader for the self-eval harness.

The manifest is a TOML file describing a growing corpus of tasks. Each task
has an id, a natural-language prompt, and metadata used for selection.

Example ``manifest.toml``::

    [[task]]
    id = "unit-add-two"
    role = "coder"
    tags = ["smoke", "python", "unit"]
    task_complexity = "single_action"
    prompt = "Write a Python function add_two(a, b) that returns a + b."
    workspace_id = "6dac22aed0e44798b04ea335a405528a"

Selection strategies:
- ``head``: first N tasks in the file (deterministic, useful for smoke runs).
- ``random``: uniform random sample without replacement (seeded per-run).
- ``tag:<name>``: filter to tasks whose ``tags`` list contains ``<name>``,
  then take the first N in file order.
"""

from __future__ import annotations

import random
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class SelfEvalTask:
    """One entry in the manifest.

    Attributes
    ----------
    id : str
        Stable, human-readable identifier. Used in artifact filenames and
        BUILD_LOG entries. Must be unique per manifest.
    role : Literal["coder", "planner"]
        Forge-OH role. Drives BFF role routing.
    task_complexity : str
        Value passed to the BFF ``taskComplexity`` field. See
        ``bff/routers/runs.py::_resolve_role``.
    prompt : str
        The natural-language task the agent will attempt.
    workspace_id : str
        Existing Forge-OH workspace UUID. The harness does NOT create
        workspaces; that is a manual, one-time setup step.
    tags : list[str]
        Free-form labels for ``--sample tag:<name>`` filtering.
    """

    id: str
    role: Literal["coder", "planner"]
    task_complexity: str
    prompt: str
    workspace_id: str
    tags: list[str] = field(default_factory=list)


class ManifestError(ValueError):
    """Raised for malformed or unusable manifests."""


def load_manifest(path: Path | str) -> list[SelfEvalTask]:
    """Parse a manifest TOML file into a list of ``SelfEvalTask``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ManifestError
        If the file is not valid TOML, has no ``[[task]]`` entries,
        or any entry is missing required fields or has a duplicate id.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"selfeval manifest not found: {p}")

    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"manifest {p} is not valid TOML: {exc}") from exc

    entries = raw.get("task")
    if not entries:
        raise ManifestError(f"manifest {p} has no [[task]] entries")
    if not isinstance(entries, list):
        raise ManifestError(f"manifest {p} 'task' must be a list of tables")

    required = ("id", "role", "task_complexity", "prompt", "workspace_id")
    tasks: list[SelfEvalTask] = []
    seen_ids: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest {p} task #{i} is not a table")
        missing = [k for k in required if k not in entry or entry[k] in (None, "")]
        if missing:
            raise ManifestError(
                f"manifest {p} task #{i} missing required fields: {missing}"
            )
        tid = str(entry["id"])
        if tid in seen_ids:
            raise ManifestError(f"manifest {p} has duplicate task id: {tid}")
        seen_ids.add(tid)
        role = entry["role"]
        if role not in ("coder", "planner"):
            raise ManifestError(
                f"manifest {p} task {tid!r}: role must be 'coder' or 'planner', got {role!r}"
            )
        tags = entry.get("tags", []) or []
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ManifestError(
                f"manifest {p} task {tid!r}: tags must be a list of strings"
            )
        tasks.append(
            SelfEvalTask(
                id=tid,
                role=role,
                task_complexity=str(entry["task_complexity"]),
                prompt=str(entry["prompt"]),
                workspace_id=str(entry["workspace_id"]),
                tags=list(tags),
            )
        )
    return tasks


def select_tasks(
    tasks: list[SelfEvalTask],
    *,
    limit: int,
    strategy: str,
    seed: int | None = None,
) -> list[SelfEvalTask]:
    """Pick a subset of ``tasks`` to run this cycle.

    Parameters
    ----------
    tasks : list[SelfEvalTask]
        All tasks parsed from the manifest.
    limit : int
        Maximum tasks to return. Must be >= 1. If greater than the number of
        candidates after filtering, returns all candidates.
    strategy : str
        ``"head"``, ``"random"``, or ``"tag:<name>"``. See module docstring.
    seed : int, optional
        Only used by ``random``. If ``None``, seeded from the OS.

    Raises
    ------
    ValueError
        For unknown strategies or non-positive limit.
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    if not tasks:
        return []

    if strategy == "head":
        candidates = tasks
    elif strategy == "random":
        rng = random.Random(seed)
        candidates = list(tasks)
        rng.shuffle(candidates)
    elif strategy.startswith("tag:"):
        tag = strategy.removeprefix("tag:").strip()
        if not tag:
            raise ValueError("tag:<name> requires a non-empty <name>")
        candidates = [t for t in tasks if tag in t.tags]
    else:
        raise ValueError(
            f"unknown selection strategy: {strategy!r} "
            "(expected 'head', 'random', or 'tag:<name>')"
        )
    return candidates[:limit]
