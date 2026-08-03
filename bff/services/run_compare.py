"""Compare two runs' file-editing activity.

Strategy (Slice X+1):
- ARTIFACTS DIFF (always): union of file paths modified by either run's
  file_editor ActionEvents. Marks each path as 'added' (only fork touched it),
  'deleted' (only base touched it), or 'modified' (both).
- CONTENT DIFF (best effort): when both runs' workspaces exist on disk, read
  the same relative path from each and produce unified line diff stats.
  Otherwise, `original`/`modified` are null and additions/deletions are 0.

Return shape matches src/lib/schemas/file-diff.ts FileDiff.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from bff.services.action_reconstruction import build_artifacts

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "shell",
    ".bash": "shell",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".txt": "plaintext",
}

_BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".7z",
    ".xz",
    ".bz2",
    ".mp3",
    ".mp4",
    ".wav",
    ".flac",
    ".ogg",
    ".webm",
    ".mov",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".class",
    ".jar",
    ".pyc",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
}


def _language_for(path: str) -> str:
    p = Path(path)
    return _LANG_BY_EXT.get(p.suffix.lower(), "plaintext")


def _is_binary_path(path: str) -> bool:
    return Path(path).suffix.lower() in _BINARY_EXTS


def _paths_from_events(events: list[dict[str, Any]], run_id: str) -> set[str]:
    """Extract distinct file paths touched by this run's file_editor actions."""
    arts = build_artifacts(events, run_id)
    return {a["path"] for a in arts if a.get("path")}


def _read_text_safe(root: str | None, rel_or_abs: str) -> str | None:
    """Read a file for content-diff purposes.

    `rel_or_abs` is the path recorded in the ActionEvent — usually absolute
    like /workspace/foo.txt. Try:
      1. The path as-is (if it exists)
      2. Under `root`, treating the path as workspace-relative
         (strip /workspace/ prefix if present)
    """
    if not rel_or_abs:
        return None
    candidates: list[Path] = []
    p = Path(rel_or_abs)
    if p.is_absolute():
        candidates.append(p)
    if root:
        root_p = Path(root)
        rel = rel_or_abs.lstrip("/")
        # Strip leading 'workspace/' if the path uses that convention.
        rel = rel.removeprefix("workspace/")
        candidates.append(root_p / rel)
    for c in candidates:
        try:
            if c.is_file() and c.stat().st_size < 5 * 1024 * 1024:  # 5MB cap
                return c.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
    return None


def _diff_counts(a: str | None, b: str | None) -> tuple[int, int]:
    """Return (additions, deletions) for unified diff a→b."""
    if a is None and b is None:
        return (0, 0)
    a_lines = (a or "").splitlines(keepends=False)
    b_lines = (b or "").splitlines(keepends=False)
    add = del_ = 0
    for line in difflib.unified_diff(a_lines, b_lines, n=0, lineterm=""):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+"):
            add += 1
        elif line.startswith("-"):
            del_ += 1
    return (add, del_)


def compare_runs(
    base_run_id: str,
    fork_run_id: str,
    base_events: list[dict[str, Any]],
    fork_events: list[dict[str, Any]],
    base_working_dir: str | None,
    fork_working_dir: str | None,
) -> dict[str, Any]:
    base_paths = _paths_from_events(base_events, base_run_id)
    fork_paths = _paths_from_events(fork_events, fork_run_id)
    all_paths = sorted(base_paths | fork_paths)

    files: list[dict[str, Any]] = []
    total_add = total_del = 0

    for path in all_paths:
        in_base = path in base_paths
        in_fork = path in fork_paths
        if in_base and not in_fork:
            status = "deleted"  # base has it, fork doesn't touch it
        elif in_fork and not in_base:
            status = "added"  # only fork introduced changes
        else:
            status = "modified"

        binary = _is_binary_path(path)
        original = None if binary else _read_text_safe(base_working_dir, path) if in_base else None
        modified = None if binary else _read_text_safe(fork_working_dir, path) if in_fork else None
        adds, dels = (0, 0) if binary else _diff_counts(original, modified)
        total_add += adds
        total_del += dels

        files.append(
            {
                "path": path,
                "status": status,
                "additions": adds,
                "deletions": dels,
                "original": original,
                "modified": modified,
                "language": _language_for(path),
                "isBinary": binary,
            }
        )

    return {
        "baseRunId": base_run_id,
        "forkRunId": fork_run_id,
        "baseTitle": f"Run {base_run_id[:8]}",
        "forkTitle": f"Run {fork_run_id[:8]}",
        "files": files,
        "stats": {
            "totalFiles": len(files),
            "additions": total_add,
            "deletions": total_del,
        },
    }
