"""bff/services/worktree.py — per-run git worktree provisioning.

Stage 6.4b (ADR-025).  Every run gets its own isolated ``git worktree``
under a configurable ``WORKTREE_ROOT`` so two concurrent runs against
the same workspace do not observe each other's file changes, and so
that a future ``POST /api/runs/{run_id}/restore`` (Stage 6.4c) can run
``git reset --hard`` inside a structurally-guaranteed-isolated path.

Design contract (ADR-025 §Decision · Stage 6.4b):

- Worktrees live under ``WORKTREE_ROOT`` (env ``FORGE_WORKTREE_ROOT``,
  default ``~/.forge-oh/worktrees/``).  One directory per run id.
- Provisioning: ``git worktree add <WORKTREE_ROOT>/<run_id> <base_ref>``
  against the source repo (the workspace's ``working_dir``).
- Teardown: ``git worktree remove <WORKTREE_ROOT>/<run_id>`` with the
  ``--force`` flag so uncommitted-but-abandoned changes don't block
  cleanup (single-user local system; deleted run == user has decided
  those changes don't matter).
- Safety guard: ``remove_worktree`` refuses to operate on any path that
  is not resolved under ``WORKTREE_ROOT``.  ``git worktree remove``'s
  own safety is insufficient — the invariant we care about is that a
  buggy caller cannot pass a hand-crafted ``run_id`` like
  ``"../../home/rmholston/dev/forge-oh"`` and wipe the source repo.

Non-goals for this module:

- Not aware of run lifecycle beyond provision/remove.  The runs router
  is responsible for calling ``provision_worktree`` on run creation
  and ``remove_worktree`` on run deletion.
- Not aware of restore/reset semantics.  Stage 6.4c will call
  ``get_worktree_path(run_id)`` and run ``git reset --hard`` itself.
- Not idempotent-by-default.  ``provision_worktree`` on an existing
  worktree raises ``WorktreeAlreadyExistsError``.  The router decides
  whether to reuse or fail; this module doesn't guess.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_WORKTREE_ROOT = Path.home() / ".forge-oh" / "worktrees"
_GIT_TIMEOUT_SEC = 30


class WorktreeError(Exception):
    """Base exception for worktree provisioning failures."""


class WorktreeAlreadyExistsError(WorktreeError):
    """Raised when provision_worktree is called for a run_id that already has one."""


class WorktreeNotFoundError(WorktreeError):
    """Raised when remove_worktree/get_worktree_path is called for an unknown run_id."""


class WorktreeSafetyError(WorktreeError):
    """Raised when a resolved path escapes WORKTREE_ROOT.

    This is a structural invariant, not a heuristic — every path we
    operate on must be a real subpath of WORKTREE_ROOT.
    """


@dataclass(frozen=True)
class WorktreeInfo:
    run_id: str
    path: Path
    source_repo: Path
    base_ref: str


def get_worktree_root() -> Path:
    """Return the resolved worktree root.

    Env override: ``FORGE_WORKTREE_ROOT``.  Default:
    ``~/.forge-oh/worktrees/``.  The directory is created on first
    call so callers don't have to.
    """
    root = Path(os.environ.get("FORGE_WORKTREE_ROOT") or _DEFAULT_WORKTREE_ROOT)
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_worktree_path(run_id: str) -> Path:
    """Return the worktree path for ``run_id`` without touching the filesystem.

    Does not verify the worktree exists.  Callers that need existence
    checks should either catch ``WorktreeNotFoundError`` from
    ``remove_worktree`` or test ``path.exists()`` themselves.
    """
    _validate_run_id(run_id)
    return get_worktree_root() / run_id


def worktree_exists(run_id: str) -> bool:
    """True if a worktree directory exists for ``run_id``.

    Does not verify git considers it a live worktree — for that, use
    ``list_worktrees`` and inspect the source repo.  This is the
    cheap "did we already provision one" check.
    """
    try:
        return get_worktree_path(run_id).is_dir()
    except WorktreeSafetyError:
        return False


def provision_worktree(
    run_id: str,
    source_repo: str | Path,
    base_ref: str = "HEAD",
) -> WorktreeInfo:
    """Create a git worktree for ``run_id`` off ``source_repo`` at ``base_ref``.

    Args:
        run_id: The BFF-visible run id.  Used verbatim as the leaf
            directory name under WORKTREE_ROOT.  Must be a plain
            identifier — no path separators, no leading dots.
        source_repo: Path to the workspace's git repo (the shared
            ``working_dir`` today).  Must be an existing git repo.
        base_ref: Git ref the new worktree checks out.  Default
            ``HEAD`` (whatever the source repo currently points at).

    Returns: WorktreeInfo describing the provisioned worktree.

    Raises:
        WorktreeAlreadyExistsError: ``run_id`` already has a worktree.
        WorktreeError: ``git worktree add`` failed, or ``source_repo``
            is not a git repo, or git is missing.
        WorktreeSafetyError: ``run_id`` resolves outside WORKTREE_ROOT.
    """
    _validate_run_id(run_id)
    source_repo_path = Path(source_repo).expanduser().resolve()
    if not source_repo_path.is_dir():
        raise WorktreeError(f"source_repo does not exist: {source_repo_path}")
    if not (source_repo_path / ".git").exists():
        # Not a repo → we can't `git worktree add` off it.  Callers
        # (the runs router) must decide whether to fall back to the
        # shared path or refuse the run.
        raise WorktreeError(
            f"source_repo is not a git repo (no .git): {source_repo_path}"
        )

    worktree_path = get_worktree_path(run_id)
    _assert_under_root(worktree_path)

    if worktree_path.exists():
        raise WorktreeAlreadyExistsError(
            f"worktree already exists for run_id={run_id!r} at {worktree_path}"
        )

    try:
        result = subprocess.run(
            ["git", "-C", str(source_repo_path), "worktree", "add",
             str(worktree_path), base_ref],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SEC,
        )
    except FileNotFoundError as e:
        raise WorktreeError("git not found in PATH") from e
    except subprocess.TimeoutExpired as e:
        raise WorktreeError(
            f"git worktree add timed out after {_GIT_TIMEOUT_SEC}s"
        ) from e

    if result.returncode != 0:
        raise WorktreeError(
            f"git worktree add failed (rc={result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    logger.info(
        "worktree provisioned: run_id=%s path=%s source=%s ref=%s",
        run_id, worktree_path, source_repo_path, base_ref,
    )
    return WorktreeInfo(
        run_id=run_id,
        path=worktree_path,
        source_repo=source_repo_path,
        base_ref=base_ref,
    )


def remove_worktree(run_id: str, *, missing_ok: bool = False) -> None:
    """Tear down the worktree for ``run_id``.

    Uses ``git worktree remove --force`` to defeat uncommitted-changes
    guards (single-user local; deleted run means the user has decided
    those changes don't matter).  If git can't clean up (e.g. the
    worktree directory was manually deleted but git's admin data
    still points at it) we fall through to ``git worktree prune`` +
    a filesystem-level ``rmtree`` scoped to WORKTREE_ROOT.

    Args:
        run_id: The run id whose worktree to remove.
        missing_ok: If True, missing worktree is a no-op.  If False
            (default), missing worktree raises WorktreeNotFoundError.

    Raises:
        WorktreeNotFoundError: run_id has no worktree and missing_ok=False.
        WorktreeSafetyError: run_id resolves outside WORKTREE_ROOT.
        WorktreeError: git operations failed unrecoverably.
    """
    _validate_run_id(run_id)
    worktree_path = get_worktree_path(run_id)
    _assert_under_root(worktree_path)

    if not worktree_path.exists():
        if missing_ok:
            return
        raise WorktreeNotFoundError(
            f"no worktree for run_id={run_id!r} at {worktree_path}"
        )

    # We need the source repo to run `git worktree remove`.  Ask git
    # about the worktree admin data before we touch anything.
    source_repo = _resolve_source_repo_for_worktree(worktree_path)

    if source_repo is not None:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_repo), "worktree", "remove",
                 "--force", str(worktree_path)],
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SEC,
            )
        except FileNotFoundError as e:
            raise WorktreeError("git not found in PATH") from e
        except subprocess.TimeoutExpired as e:
            raise WorktreeError(
                f"git worktree remove timed out after {_GIT_TIMEOUT_SEC}s"
            ) from e

        if result.returncode == 0:
            logger.info(
                "worktree removed: run_id=%s path=%s source=%s",
                run_id, worktree_path, source_repo,
            )
            return

        # Fall through to prune + rmtree.  Log the git error so it's
        # discoverable in bff.log; DEBUG_LOG-worthy if we see it often.
        logger.warning(
            "git worktree remove failed for run_id=%s (rc=%d): %s — falling back to prune+rmtree",
            run_id, result.returncode,
            result.stderr.strip() or result.stdout.strip(),
        )

    # Filesystem fallback.  _assert_under_root above already guarantees
    # worktree_path is a WORKTREE_ROOT subpath; rmtree is safe here.
    if worktree_path.exists():
        shutil.rmtree(worktree_path)

    if source_repo is not None:
        # Best-effort prune to clean up git admin state.  Ignore rc.
        subprocess.run(
            ["git", "-C", str(source_repo), "worktree", "prune"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SEC,
        )

    logger.info(
        "worktree removed via fallback: run_id=%s path=%s",
        run_id, worktree_path,
    )


def list_worktrees() -> list[Path]:
    """Return every worktree directory currently under WORKTREE_ROOT.

    Filesystem-level only; does not consult git.  Used by health
    endpoints and tests that want to enumerate active runs' worktrees.
    """
    root = get_worktree_root()
    return sorted(p for p in root.iterdir() if p.is_dir())


# ─── internals ──────────────────────────────────────────────────────


def _validate_run_id(run_id: str) -> None:
    if not run_id or not isinstance(run_id, str):
        raise WorktreeSafetyError(f"invalid run_id: {run_id!r}")
    if "/" in run_id or "\\" in run_id or run_id.startswith(".") or ".." in run_id:
        raise WorktreeSafetyError(
            f"run_id contains path separators or traversal: {run_id!r}"
        )


def _assert_under_root(path: Path) -> None:
    """Structural invariant: path must be a real subpath of WORKTREE_ROOT.

    Uses ``Path.is_relative_to`` (3.9+) after ``.resolve()`` to defeat
    symlink and ``..`` shenanigans.  If this assertion ever fires we
    have a caller bug; treat it as fatal, not recoverable.
    """
    root = get_worktree_root()
    resolved = path.resolve() if path.exists() else (root / path.name).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise WorktreeSafetyError(
            f"path escapes WORKTREE_ROOT: path={resolved} root={root}"
        ) from e


def _resolve_source_repo_for_worktree(worktree_path: Path) -> Path | None:
    """Ask git which repo owns this worktree.

    Reads ``<worktree>/.git`` which for a worktree is a *file* (not a
    dir) whose content is ``gitdir: /path/to/source/.git/worktrees/<name>``.
    From that we walk up to the source repo root.

    Returns None if the .git pointer is missing/malformed — the caller
    falls back to filesystem-level cleanup.
    """
    dotgit = worktree_path / ".git"
    if not dotgit.is_file():
        return None
    try:
        content = dotgit.read_text().strip()
    except OSError:
        return None
    prefix = "gitdir: "
    if not content.startswith(prefix):
        return None
    gitdir = Path(content[len(prefix):])
    # gitdir is /path/to/source/.git/worktrees/<name>
    # walk up to .../.git → parent is the source repo root.
    for parent in gitdir.parents:
        if parent.name == ".git":
            return parent.parent
    return None
