"""Tests for the test-runner selector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openhands_tools_ext.verify.schema import VerifyRunner
from openhands_tools_ext.verify.selector import (
    RunnerConfig,
    build_command,
    detect_runner,
    select_targets,
)


class TestDetectRunner:
    def test_missing_workspace_returns_none(self, tmp_path: Path) -> None:
        assert detect_runner(tmp_path / "does-not-exist") is None

    def test_empty_workspace_returns_none(self, tmp_path: Path) -> None:
        assert detect_runner(tmp_path) is None

    def test_pyproject_selects_pytest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        cfg = detect_runner(tmp_path)
        assert cfg is not None
        assert cfg.runner == VerifyRunner.PYTEST
        assert cfg.command_prefix[0] == "pytest"

    def test_vitest_config_selects_vitest(self, tmp_path: Path) -> None:
        (tmp_path / "vitest.config.ts").write_text("export default {}\n")
        cfg = detect_runner(tmp_path)
        assert cfg is not None
        assert cfg.runner == VerifyRunner.VITEST
        assert cfg.command_prefix[:2] == ["npx", "vitest"]

    def test_jest_config_selects_jest(self, tmp_path: Path) -> None:
        (tmp_path / "jest.config.js").write_text("module.exports = {}\n")
        cfg = detect_runner(tmp_path)
        assert cfg is not None
        assert cfg.runner == VerifyRunner.JEST

    def test_package_json_with_test_script_selects_npm_test(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "x", "scripts": {"test": "echo hi"}})
        )
        cfg = detect_runner(tmp_path)
        assert cfg is not None
        assert cfg.runner == VerifyRunner.NPM_TEST

    def test_package_json_without_test_script_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "x", "scripts": {"build": "echo hi"}})
        )
        assert detect_runner(tmp_path) is None

    def test_pyproject_wins_over_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "x", "scripts": {"test": "echo hi"}})
        )
        cfg = detect_runner(tmp_path)
        assert cfg is not None
        assert cfg.runner == VerifyRunner.PYTEST

    def test_vitest_wins_over_jest_when_both_configs_exist(self, tmp_path: Path) -> None:
        (tmp_path / "vitest.config.ts").write_text("export default {}\n")
        (tmp_path / "jest.config.js").write_text("module.exports = {}\n")
        cfg = detect_runner(tmp_path)
        assert cfg is not None
        assert cfg.runner == VerifyRunner.VITEST

    def test_malformed_package_json_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{ not json")
        assert detect_runner(tmp_path) is None


class TestSelectTargetsPython:
    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("def foo(): pass\n")
        (tmp_path / "src" / "bar.py").write_text("def bar(): pass\n")
        (tmp_path / "src" / "test_foo.py").write_text("def test_foo(): pass\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_bar.py").write_text("def test_bar(): pass\n")
        return tmp_path

    def test_edited_test_file_is_its_own_target(self, repo: Path) -> None:
        result = select_targets(repo, [repo / "src" / "test_foo.py"], VerifyRunner.PYTEST)
        assert result == ["src/test_foo.py"]

    def test_edited_source_finds_sibling_test(self, repo: Path) -> None:
        result = select_targets(repo, [repo / "src" / "foo.py"], VerifyRunner.PYTEST)
        assert result == ["src/test_foo.py"]

    def test_edited_source_without_sibling_falls_back_to_dir(self, repo: Path) -> None:
        # bar.py has no sibling test_bar.py in src/, but src/ contains
        # test_foo.py so the dir-level fallback picks src/.
        result = select_targets(repo, [repo / "src" / "bar.py"], VerifyRunner.PYTEST)
        assert result == ["src"]

    def test_multiple_edited_files_deduplicated(self, repo: Path) -> None:
        result = select_targets(
            repo,
            [repo / "src" / "foo.py", repo / "src" / "bar.py"],
            VerifyRunner.PYTEST,
        )
        # foo.py -> src/test_foo.py; bar.py -> src (fallback). Both distinct.
        assert set(result) == {"src/test_foo.py", "src"}

    def test_nonexistent_edited_file_is_ignored(self, repo: Path) -> None:
        result = select_targets(repo, [repo / "src" / "ghost.py"], VerifyRunner.PYTEST)
        assert result == []

    def test_relative_edited_paths_supported(self, repo: Path) -> None:
        result = select_targets(repo, ["src/test_foo.py"], VerifyRunner.PYTEST)
        assert result == ["src/test_foo.py"]

    def test_edited_file_outside_workspace_ignored(self, repo: Path, tmp_path: Path) -> None:
        elsewhere = tmp_path.parent / f"outside-{tmp_path.name}.py"
        elsewhere.write_text("x = 1\n")
        try:
            result = select_targets(repo, [elsewhere], VerifyRunner.PYTEST)
            assert result == []
        finally:
            elsewhere.unlink(missing_ok=True)


class TestSelectTargetsJS:
    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "add.ts").write_text("export const add = (a,b)=>a+b\n")
        (tmp_path / "src" / "add.test.ts").write_text("test('x',()=>{})\n")
        (tmp_path / "src" / "sub.ts").write_text("export const sub = (a,b)=>a-b\n")
        return tmp_path

    def test_edited_source_finds_sibling_dot_test(self, repo: Path) -> None:
        result = select_targets(repo, [repo / "src" / "add.ts"], VerifyRunner.VITEST)
        assert result == ["src/add.test.ts"]

    def test_edited_test_file_is_its_own_target(self, repo: Path) -> None:
        result = select_targets(repo, [repo / "src" / "add.test.ts"], VerifyRunner.VITEST)
        assert result == ["src/add.test.ts"]

    def test_source_without_sibling_falls_back_to_dir_with_tests(self, repo: Path) -> None:
        result = select_targets(repo, [repo / "src" / "sub.ts"], VerifyRunner.VITEST)
        assert result == ["src"]


class TestBuildCommand:
    def test_command_prefix_prepended(self) -> None:
        cfg = RunnerConfig(
            runner=VerifyRunner.PYTEST,
            command_prefix=["pytest", "-x", "-q"],
        )
        assert build_command(cfg, ["a.py", "b.py"]) == [
            "pytest",
            "-x",
            "-q",
            "a.py",
            "b.py",
        ]

    def test_empty_targets_yields_prefix_only(self) -> None:
        cfg = RunnerConfig(
            runner=VerifyRunner.VITEST,
            command_prefix=["npx", "vitest", "run"],
        )
        assert build_command(cfg, []) == ["npx", "vitest", "run"]
