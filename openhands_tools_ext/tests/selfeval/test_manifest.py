"""Tests for the selfeval manifest loader + selector."""

from __future__ import annotations

from pathlib import Path

import pytest

from openhands_tools_ext.selfeval.manifest import (
    ManifestError,
    SelfEvalTask,
    load_manifest,
    select_tasks,
)


def _write_manifest(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "manifest.toml"
    p.write_text(body, encoding="utf-8")
    return p


VALID_ENTRY = """
[[task]]
id = "t1"
role = "coder"
task_complexity = "single_action"
workspace_id = "ws-1"
prompt = "do a thing"
tags = ["smoke"]
"""


class TestLoadManifest:
    def test_loads_valid(self, tmp_path: Path) -> None:
        p = _write_manifest(tmp_path, VALID_ENTRY)
        tasks = load_manifest(p)
        assert len(tasks) == 1
        assert tasks[0].id == "t1"
        assert tasks[0].role == "coder"
        assert tasks[0].tags == ["smoke"]

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "nope.toml")

    def test_invalid_toml(self, tmp_path: Path) -> None:
        p = _write_manifest(tmp_path, "not = valid = toml")
        with pytest.raises(ManifestError, match="not valid TOML"):
            load_manifest(p)

    def test_no_task_entries(self, tmp_path: Path) -> None:
        p = _write_manifest(tmp_path, 'other = "field"\n')
        with pytest.raises(ManifestError, match="no \\[\\[task\\]\\] entries"):
            load_manifest(p)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        p = _write_manifest(
            tmp_path,
            '[[task]]\nid = "t1"\nrole = "coder"\nprompt = "p"\ntask_complexity = "single_action"\n',
        )
        with pytest.raises(ManifestError, match="missing required fields"):
            load_manifest(p)

    def test_duplicate_id(self, tmp_path: Path) -> None:
        p = _write_manifest(tmp_path, VALID_ENTRY + VALID_ENTRY)
        with pytest.raises(ManifestError, match="duplicate task id"):
            load_manifest(p)

    def test_invalid_role(self, tmp_path: Path) -> None:
        p = _write_manifest(
            tmp_path,
            VALID_ENTRY.replace('role = "coder"', 'role = "auditor"'),
        )
        with pytest.raises(ManifestError, match="role must be"):
            load_manifest(p)

    def test_invalid_tags_type(self, tmp_path: Path) -> None:
        p = _write_manifest(
            tmp_path,
            VALID_ENTRY.replace('tags = ["smoke"]', 'tags = "smoke"'),
        )
        with pytest.raises(ManifestError, match="tags must be a list"):
            load_manifest(p)


def _mk(id_: str, tags: list[str] | None = None, role: str = "coder") -> SelfEvalTask:
    return SelfEvalTask(
        id=id_,
        role=role,  # type: ignore[arg-type]
        task_complexity="single_action",
        prompt="p",
        workspace_id="ws",
        tags=tags or [],
    )


class TestSelectTasks:
    def test_head_returns_first_n(self) -> None:
        tasks = [_mk(f"t{i}") for i in range(5)]
        out = select_tasks(tasks, limit=3, strategy="head")
        assert [t.id for t in out] == ["t0", "t1", "t2"]

    def test_head_limit_exceeds_returns_all(self) -> None:
        tasks = [_mk(f"t{i}") for i in range(2)]
        out = select_tasks(tasks, limit=10, strategy="head")
        assert len(out) == 2

    def test_random_is_seeded(self) -> None:
        tasks = [_mk(f"t{i}") for i in range(10)]
        a = select_tasks(tasks, limit=5, strategy="random", seed=42)
        b = select_tasks(tasks, limit=5, strategy="random", seed=42)
        c = select_tasks(tasks, limit=5, strategy="random", seed=7)
        assert [t.id for t in a] == [t.id for t in b]
        assert [t.id for t in a] != [t.id for t in c]

    def test_tag_filter(self) -> None:
        tasks = [
            _mk("t0", tags=["smoke"]),
            _mk("t1", tags=["long"]),
            _mk("t2", tags=["smoke", "long"]),
        ]
        out = select_tasks(tasks, limit=10, strategy="tag:smoke")
        assert {t.id for t in out} == {"t0", "t2"}

    def test_tag_empty_name(self) -> None:
        with pytest.raises(ValueError, match="requires a non-empty"):
            select_tasks([_mk("t0")], limit=1, strategy="tag:")

    def test_unknown_strategy(self) -> None:
        with pytest.raises(ValueError, match="unknown selection strategy"):
            select_tasks([_mk("t0")], limit=1, strategy="chaos")

    def test_zero_limit(self) -> None:
        with pytest.raises(ValueError, match="limit must be >= 1"):
            select_tasks([_mk("t0")], limit=0, strategy="head")

    def test_empty_tasks(self) -> None:
        assert select_tasks([], limit=5, strategy="head") == []
