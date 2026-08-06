"""Stage 6.4b — bff.services.worktree unit tests (ADR-025).

Covers:
  * provision_worktree happy path (creates dir under WORKTREE_ROOT, is a
    real git worktree, has correct base_ref checked out).
  * WORKTREE_ROOT env override honoured.
  * provision_worktree on existing run_id raises WorktreeAlreadyExistsError.
  * provision_worktree against a non-git dir raises WorktreeError.
  * provision_worktree against a non-existent dir raises WorktreeError.
  * remove_worktree happy path (removes the dir AND git's admin state).
  * remove_worktree with missing_ok=True on unknown run_id is a no-op.
  * remove_worktree with missing_ok=False on unknown run_id raises
    WorktreeNotFoundError.
  * remove_worktree filesystem-fallback path (git admin data missing).
  * Safety guard: path-traversal / absolute / separator run_ids rejected.
  * Safety guard: _assert_under_root refuses to operate on paths that
    resolve outside WORKTREE_ROOT (regression against a caller bug).
  * list_worktrees enumerates only real subdirectories of WORKTREE_ROOT.
  * Two concurrent worktrees off the same source repo do not observe
    each other's file changes — the actual isolation invariant that
    the 6.4b DoD hinges on.

Uses tmp_path per test to keep filesystem state isolated.  All tests
override ``FORGE_WORKTREE_ROOT`` via monkeypatch so no test ever
touches ``~/.forge-oh/worktrees/``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bff.services import worktree as wt


# ─── fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def worktree_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override FORGE_WORKTREE_ROOT to a temp dir for this test."""
    root = tmp_path / "worktrees"
    monkeypatch.setenv("FORGE_WORKTREE_ROOT", str(root))
    return root


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """Create a real git repo under tmp_path/source with one initial commit."""
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@forge-oh.test"],
        cwd=repo, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo, check=True,
    )
    # An initial commit is required for `git worktree add HEAD`.
    (repo / "README.md").write_text("initial\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "initial"],
        cwd=repo, check=True,
    )
    # `git worktree add` off HEAD needs a branch OTHER than the current
    # one when HEAD is on a branch (worktrees can't share a branch by
    # default).  Detached HEAD works, so we detach.
    subprocess.run(["git", "checkout", "-q", "--detach"], cwd=repo, check=True)
    return repo


# ─── env / root resolution ──────────────────────────────────────────


def test_get_worktree_root_uses_env_override(worktree_root: Path) -> None:
    assert wt.get_worktree_root() == worktree_root.resolve()
    assert worktree_root.exists()  # created on first call


def test_get_worktree_root_default_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent env → default ~/.forge-oh/worktrees/ (resolved)."""
    monkeypatch.delenv("FORGE_WORKTREE_ROOT", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    root = wt.get_worktree_root()
    assert root == (tmp_path / ".forge-oh" / "worktrees").resolve()


# ─── provision_worktree ─────────────────────────────────────────────


def test_provision_worktree_happy_path(
    worktree_root: Path, source_repo: Path,
) -> None:
    info = wt.provision_worktree("run-1", source_repo)
    assert info.run_id == "run-1"
    assert info.path == worktree_root.resolve() / "run-1"
    assert info.source_repo == source_repo.resolve()
    assert info.base_ref == "HEAD"
    assert info.path.is_dir()
    # git recognises it as a real worktree
    assert (info.path / ".git").is_file()  # worktree .git is a pointer file
    assert (info.path / "README.md").read_text() == "initial\n"


def test_provision_worktree_registers_with_source_repo(
    worktree_root: Path, source_repo: Path,
) -> None:
    wt.provision_worktree("run-a", source_repo)
    listing = subprocess.run(
        ["git", "-C", str(source_repo), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert str(worktree_root.resolve() / "run-a") in listing


def test_provision_worktree_duplicate_raises(
    worktree_root: Path, source_repo: Path,
) -> None:
    wt.provision_worktree("run-dup", source_repo)
    with pytest.raises(wt.WorktreeAlreadyExistsError):
        wt.provision_worktree("run-dup", source_repo)


def test_provision_worktree_nongit_source_raises(
    worktree_root: Path, tmp_path: Path,
) -> None:
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    with pytest.raises(wt.WorktreeError, match="not a git repo"):
        wt.provision_worktree("run-x", not_a_repo)


def test_provision_worktree_nonexistent_source_raises(
    worktree_root: Path, tmp_path: Path,
) -> None:
    with pytest.raises(wt.WorktreeError, match="does not exist"):
        wt.provision_worktree("run-x", tmp_path / "no-such-dir")


# ─── remove_worktree ────────────────────────────────────────────────


def test_remove_worktree_happy_path(
    worktree_root: Path, source_repo: Path,
) -> None:
    info = wt.provision_worktree("run-r", source_repo)
    assert info.path.exists()
    wt.remove_worktree("run-r")
    assert not info.path.exists()
    # git's admin state also cleaned up
    listing = subprocess.run(
        ["git", "-C", str(source_repo), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "run-r" not in listing


def test_remove_worktree_missing_ok_true_is_noop(worktree_root: Path) -> None:
    # No exception even though nothing exists yet.
    wt.remove_worktree("nonexistent", missing_ok=True)


def test_remove_worktree_missing_ok_false_raises(worktree_root: Path) -> None:
    with pytest.raises(wt.WorktreeNotFoundError):
        wt.remove_worktree("nonexistent")


def test_remove_worktree_filesystem_fallback(
    worktree_root: Path, source_repo: Path,
) -> None:
    """If .git pointer is missing (manual meddling), fall through to rmtree."""
    info = wt.provision_worktree("run-fb", source_repo)
    # Simulate corruption: delete the .git pointer file so git can't
    # locate the source repo from the worktree.  remove_worktree must
    # still succeed via the fs-fallback path.
    (info.path / ".git").unlink()
    wt.remove_worktree("run-fb")
    assert not info.path.exists()


# ─── safety guard ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        "..",
        "../escape",
        "sub/run",
        "sub\\run",
        ".hidden",
        "..sneaky",
    ],
)
def test_bad_run_id_rejected(worktree_root: Path, bad_id: str) -> None:
    with pytest.raises(wt.WorktreeSafetyError):
        wt.get_worktree_path(bad_id)


def test_safety_guard_never_touches_outside_root(
    worktree_root: Path, source_repo: Path, tmp_path: Path,
) -> None:
    """No matter what caller-crafted path we try to resolve, we never
    end up operating outside WORKTREE_ROOT.  Regression guard for a
    hypothetical future caller bug.
    """
    outside = tmp_path / "outside-root"
    outside.mkdir()
    # _assert_under_root should reject this path even though it exists.
    with pytest.raises(wt.WorktreeSafetyError):
        wt._assert_under_root(outside)


# ─── list_worktrees ─────────────────────────────────────────────────


def test_list_worktrees_enumerates_provisioned(
    worktree_root: Path, source_repo: Path,
) -> None:
    assert wt.list_worktrees() == []
    wt.provision_worktree("run-1", source_repo)
    wt.provision_worktree("run-2", source_repo)
    listed = wt.list_worktrees()
    names = [p.name for p in listed]
    assert names == sorted(["run-1", "run-2"])


# ─── isolation invariant (the 6.4b DoD) ─────────────────────────────


def test_concurrent_worktrees_do_not_observe_each_others_writes(
    worktree_root: Path, source_repo: Path,
) -> None:
    """Stage 6.4b DoD: two runs against the same source repo see
    independent working directories.  If this test ever regresses, the
    whole point of the slice is broken.
    """
    a = wt.provision_worktree("run-A", source_repo)
    b = wt.provision_worktree("run-B", source_repo)

    (a.path / "unique-to-a.txt").write_text("only in A\n")
    (b.path / "unique-to-b.txt").write_text("only in B\n")

    # Cross-visibility must be zero.
    assert not (a.path / "unique-to-b.txt").exists()
    assert not (b.path / "unique-to-a.txt").exists()

    # And neither leaks into the source repo (which is on detached HEAD
    # per the fixture — the worktree branches don't share HEAD).
    assert not (source_repo / "unique-to-a.txt").exists()
    assert not (source_repo / "unique-to-b.txt").exists()


def test_worktree_exists_true_after_provision_false_after_remove(
    worktree_root: Path, source_repo: Path,
) -> None:
    assert not wt.worktree_exists("run-lifecycle")
    wt.provision_worktree("run-lifecycle", source_repo)
    assert wt.worktree_exists("run-lifecycle")
    wt.remove_worktree("run-lifecycle")
    assert not wt.worktree_exists("run-lifecycle")


def test_worktree_exists_bad_id_returns_false(worktree_root: Path) -> None:
    """Safety-check convenience: bad ids are non-existent, not exceptions."""
    assert wt.worktree_exists("../evil") is False
