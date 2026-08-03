"""Reconstruct per-run file state from agent-server event stream.

Rationale: the agent operates inside a sandboxed filesystem the BFF can't
read directly (paths like /workspace/foo.txt live inside the agent-server
container). Every file mutation, however, is fully recorded in
FileEditorObservation events with the resulting content. We rebuild the
per-run file set by folding those observations in timestamp order.

Supported FileEditorObservation.command values:
  * ``create``       — first write; ``new_content`` = full content.
  * ``str_replace``  — partial edit; ``new_content`` = full content after,
                       ``old_content`` = full content before.
  * ``insert``       — same shape as ``str_replace``.
  * ``undo_edit``    — reverts to prior state; ``new_content`` = restored.
  * ``view``         — read-only, ignored.

Fields used from the observation:
  is_error, command, path, prev_exist, new_content, old_content
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

_MUTATING_COMMANDS = {"create", "str_replace", "insert", "undo_edit"}

_LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".txt": "plaintext",
}


def _guess_language(path: str) -> str:
    lower = path.lower()
    if "." not in lower.rsplit("/", 1)[-1]:
        return "plaintext"
    ext = "." + lower.rsplit(".", 1)[-1]
    return _LANGUAGE_BY_EXT.get(ext, "plaintext")


def _is_binary_text(text: str | None) -> bool:
    if text is None:
        return False
    # OpenHands FileEditorObservation returns strings; a null byte or
    # a decoding-fail marker indicates binary. Cheap heuristic.
    return "\x00" in text


def _line_stats(original: str | None, modified: str | None) -> tuple[int, int]:
    """Return (additions, deletions) using unified line diff."""
    orig_lines = (original or "").splitlines()
    mod_lines = (modified or "").splitlines()
    additions = 0
    deletions = 0
    for line in difflib.unified_diff(orig_lines, mod_lines, n=0, lineterm=""):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


@dataclass
class _FileState:
    path: str
    original: str | None = None  # content BEFORE first mutation in this run
    modified: str | None = None  # content AFTER last mutation
    prev_exist_at_first_touch: bool = False
    touched: bool = False

    def apply(self, command: str, old_content: str | None, new_content: str | None, prev_exist: bool) -> None:
        if not self.touched:
            # First time we see this path in the run
            self.prev_exist_at_first_touch = bool(prev_exist)
            # For 'create' when file didn't previously exist, original=None (added).
            # For 'create' overwriting, original=old_content (typically None from server).
            # For 'str_replace'/'insert', old_content is the pre-edit content.
            if command == "create":
                self.original = old_content if prev_exist else None
            else:
                self.original = old_content
            self.touched = True
        self.modified = new_content

    def status(self) -> str:
        if not self.prev_exist_at_first_touch:
            return "added"
        return "modified"


def _iter_events(events: list[dict[str, Any]]):
    """Yield (path, command, old_content, new_content, prev_exist) tuples."""
    for evt in events:
        if evt.get("kind") != "ObservationEvent":
            continue
        obs = evt.get("observation") or {}
        if obs.get("kind") != "FileEditorObservation":
            continue
        if obs.get("is_error"):
            continue
        command = obs.get("command")
        if command not in _MUTATING_COMMANDS:
            continue
        path = obs.get("path")
        if not path:
            continue
        yield (
            path,
            command,
            obs.get("old_content"),
            obs.get("new_content"),
            bool(obs.get("prev_exist")),
        )


def reconstruct(events: list[dict[str, Any]]) -> dict[str, _FileState]:
    """Fold ordered events into a {path: _FileState} map."""
    state: dict[str, _FileState] = {}
    for path, command, old_content, new_content, prev_exist in _iter_events(events):
        fs = state.setdefault(path, _FileState(path=path))
        fs.apply(command, old_content, new_content, prev_exist)
    return state


def _summary(fs: _FileState) -> dict[str, Any]:
    is_bin = _is_binary_text(fs.original) or _is_binary_text(fs.modified)
    additions, deletions = (0, 0) if is_bin else _line_stats(fs.original, fs.modified)
    return {
        "path": fs.path,
        "status": fs.status(),
        "additions": additions,
        "deletions": deletions,
        "language": _guess_language(fs.path),
        "isBinary": is_bin,
    }


def build_summaries(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state = reconstruct(events)
    out = [_summary(fs) for fs in state.values()]
    out.sort(key=lambda f: f["path"])
    return out


def build_file_diff(events: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    state = reconstruct(events)
    fs = state.get(path)
    if fs is None:
        return None
    summary = _summary(fs)
    return {
        **summary,
        "original": fs.original,
        "modified": fs.modified,
    }
