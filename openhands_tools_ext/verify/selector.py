"""Test-runner auto-detection and target selection.

Given a workspace root and a set of recently-edited files, pick:
  1. Which test runner to invoke (pytest / vitest / jest / npm_test).
  2. The narrowest set of test targets that covers the edited files.

Design goals:
  - Deterministic. Same inputs -> same output. Pure functions of the
    filesystem state, no LLM calls.
  - Cheap. No fs walk beyond a bounded depth; no test file parsing.
  - Fail-open. If nothing sensible can be selected, return
    (UNKNOWN, [], "") rather than raising -- the caller emits a
    ``verdict=skipped`` event and moves on.

Selection order per edited file:
  1. If the file *is* a test file already, use it directly.
  2. Look for a sibling test file matching a canonical pattern
     (``test_<name>.py`` / ``<name>.test.ts`` / etc.).
  3. Fall back to the directory containing the file, if any test file
     lives in it.
  4. Fall back to the top-level project test directory (``tests/``,
     ``__tests__/``, or the runner's default) if the runner exists at
     all.

Runner detection: look for the project's config files (``pyproject.toml``
with a ``[tool.pytest]`` section, ``vitest.config.ts``, ``jest.config.*``,
or a ``package.json`` with a ``test`` script) starting at the workspace
root. Uses only the workspace root's filesystem; does not traverse into
node_modules or vendored code.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from openhands_tools_ext.verify.schema import VerifyRunner

# ---------------------------------------------------------------------------
# Runner detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunnerConfig:
    """A detected runner plus the command prefix used to invoke it."""

    runner: VerifyRunner
    # Command prefix to prepend to test targets. Rendered verbatim with
    # targets appended. Empty list means "no test targets, run everything".
    command_prefix: list[str]


def detect_runner(workspace: Path) -> RunnerConfig | None:
    """Detect the project's test runner from filesystem markers.

    Order of preference matches how humans read the repo root: Python
    projects first (pyproject.toml is the most common Python marker),
    then JS/TS. If multiple markers exist (a polyglot repo), return the
    Python runner -- Forge-OH's own repo is that case and pytest is the
    primary loop for backend edits.

    Returns None if no runner can be detected.
    """
    if not workspace.is_dir():
        return None

    pyproject = workspace / "pyproject.toml"
    if pyproject.is_file():
        # Any pyproject with a src/tests layout or a [tool.pytest] section
        # is a pytest project. Cheap check: just require pyproject exists;
        # if pytest isn't installed the subprocess call will fail with a
        # clear stderr, which the caller records verbatim.
        return RunnerConfig(
            runner=VerifyRunner.PYTEST,
            command_prefix=["pytest", "-x", "--no-header", "-q"],
        )

    # vitest takes precedence over jest because it's the recommended
    # runner for new Vite/Next.js projects and Forge-OH itself uses it.
    if (workspace / "vitest.config.ts").is_file() or (workspace / "vitest.config.js").is_file():
        return RunnerConfig(
            runner=VerifyRunner.VITEST,
            command_prefix=["npx", "vitest", "run", "--reporter=verbose"],
        )

    if any(
        (workspace / name).is_file()
        for name in ("jest.config.js", "jest.config.ts", "jest.config.mjs")
    ):
        return RunnerConfig(
            runner=VerifyRunner.JEST,
            command_prefix=["npx", "jest", "--no-coverage"],
        )

    package_json = workspace / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            return None
        scripts = (data or {}).get("scripts") or {}
        if "test" in scripts:
            return RunnerConfig(
                runner=VerifyRunner.NPM_TEST,
                command_prefix=["npm", "test", "--"],
            )

    return None


# ---------------------------------------------------------------------------
# Target selection
# ---------------------------------------------------------------------------


_PYTHON_TEST_PATTERNS = ("test_", "_test")
_JS_TEST_PATTERNS = (".test.", ".spec.")


def _is_python_test(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    stem = path.stem
    return stem.startswith("test_") or stem.endswith("_test")


def _is_js_test(path: Path) -> bool:
    if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}:
        return False
    name = path.name
    return ".test." in name or ".spec." in name


def _sibling_test_for(path: Path, runner: VerifyRunner) -> Path | None:
    """Return a sibling test file if one exists next to ``path``."""
    if not path.is_file():
        return None
    parent = path.parent
    stem = path.stem
    if runner == VerifyRunner.PYTEST:
        for cand in (parent / f"test_{stem}.py", parent / f"{stem}_test.py"):
            if cand.is_file():
                return cand
        # Also look in a sibling ``tests/`` directory next to the file's
        # package.
        tests_dir = parent / "tests"
        if tests_dir.is_dir():
            for cand in tests_dir.iterdir():
                if cand.is_file() and _is_python_test(cand) and stem in cand.stem:
                    return cand
        return None
    if runner in (VerifyRunner.VITEST, VerifyRunner.JEST, VerifyRunner.NPM_TEST):
        for suffix in (".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx"):
            cand = parent / f"{stem}{suffix}"
            if cand.is_file():
                return cand
        return None
    return None


def _dir_has_tests(directory: Path, runner: VerifyRunner) -> bool:
    if not directory.is_dir():
        return False
    for child in directory.iterdir():
        if not child.is_file():
            continue
        if runner == VerifyRunner.PYTEST and _is_python_test(child):
            return True
        if runner in (
            VerifyRunner.VITEST,
            VerifyRunner.JEST,
            VerifyRunner.NPM_TEST,
        ) and _is_js_test(child):
            return True
    return False


def select_targets(
    workspace: Path,
    edited_files: Iterable[str | Path],
    runner: VerifyRunner,
) -> list[str]:
    """Pick the narrowest set of test targets covering ``edited_files``.

    Returned paths are workspace-relative POSIX strings, suitable to
    append directly to the runner command prefix.
    """
    edited_paths = [Path(p) for p in edited_files]
    workspace = workspace.resolve()
    seen: set[str] = set()
    targets: list[str] = []

    def _add(p: Path) -> None:
        try:
            rel = p.resolve().relative_to(workspace).as_posix()
        except ValueError:
            return
        if rel not in seen:
            seen.add(rel)
            targets.append(rel)

    for original in edited_paths:
        p = original if original.is_absolute() else (workspace / original)
        if not p.exists():
            continue
        # 1. File itself is a test -> use it.
        if runner == VerifyRunner.PYTEST and _is_python_test(p):
            _add(p)
            continue
        if runner != VerifyRunner.PYTEST and _is_js_test(p):
            _add(p)
            continue
        # 2. Sibling test.
        sibling = _sibling_test_for(p, runner)
        if sibling is not None:
            _add(sibling)
            continue
        # 3. Directory-level fallback: only if that directory actually
        # has test files.
        parent = p.parent
        if _dir_has_tests(parent, runner):
            _add(parent)
            continue
        # Else skip this edited file; another edited file may cover it.

    return targets


def build_command(config: RunnerConfig, targets: list[str]) -> list[str]:
    """Compose the final argv for subprocess.run."""
    return list(config.command_prefix) + list(targets)
