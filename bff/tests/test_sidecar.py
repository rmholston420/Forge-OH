"""Tests for :mod:`bff.services.sidecar` (Slice F.12).

These tests hit the pure sidecar-writer module directly. Router-level
integration (that :mod:`bff.routers.runs` actually calls the seeder) is
covered separately in :mod:`bff.tests.test_hook_config` where the
create-run flow is already mocked out.
"""

from __future__ import annotations

import json
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bff.services.sidecar import seed_sidecar, sidecar_path, update_sidecar


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A fresh workspace directory for each test."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


class TestSidecarPath:
    def test_path_layout_matches_hook_contract(self, workspace: Path) -> None:
        """Path must be ``$WORKSPACE/.forge-oh/trajectory-sidecar.json``.

        This is the *contract* the trajectory hook reads from — changing
        either side without the other silently breaks the pipeline.
        """
        p = sidecar_path(workspace)
        assert p == workspace / ".forge-oh" / "trajectory-sidecar.json"

    def test_accepts_string_paths(self, workspace: Path) -> None:
        p = sidecar_path(str(workspace))
        assert p.name == "trajectory-sidecar.json"
        assert p.parent.name == ".forge-oh"


class TestSeedSidecar:
    def test_creates_state_dir_if_missing(self, workspace: Path) -> None:
        assert not (workspace / ".forge-oh").exists()
        result = seed_sidecar(
            workspace=workspace, session_id="sess-1", task_description="do X"
        )
        assert result is not None
        assert (workspace / ".forge-oh").is_dir()
        assert result.exists()

    def test_writes_task_description_keyed_by_session_id(
        self, workspace: Path
    ) -> None:
        seed_sidecar(
            workspace=workspace,
            session_id="conv-abc",
            task_description="fix the failing test",
        )
        payload = json.loads(sidecar_path(workspace).read_text())
        # Session id is the top-level key (matches verify-state.json layout).
        assert "conv-abc" in payload
        assert payload["conv-abc"]["task_description"] == "fix the failing test"

    def test_multiple_sessions_coexist(self, workspace: Path) -> None:
        """Seeding session B must not clobber session A."""
        seed_sidecar(
            workspace=workspace, session_id="sess-A", task_description="task A"
        )
        seed_sidecar(
            workspace=workspace, session_id="sess-B", task_description="task B"
        )
        payload = json.loads(sidecar_path(workspace).read_text())
        assert payload["sess-A"]["task_description"] == "task A"
        assert payload["sess-B"]["task_description"] == "task B"

    def test_reseeding_preserves_downstream_fields(self, workspace: Path) -> None:
        """A downstream producer's fields must survive a re-seed."""
        # Downstream planner filled in extra fields.
        update_sidecar(
            workspace=workspace,
            session_id="sess-1",
            fields={
                "task_description": "original",
                "plan": "step 1; step 2",
                "repograph_symbols": ["a.b", "c.d"],
            },
        )
        # Re-seed with a new task description — but plan+symbols must survive.
        seed_sidecar(
            workspace=workspace,
            session_id="sess-1",
            task_description="overridden",
        )
        payload = json.loads(sidecar_path(workspace).read_text())
        slot = payload["sess-1"]
        # Empty-check semantics: seeder only overwrites when existing is empty.
        assert slot["task_description"] == "original"
        assert slot["plan"] == "step 1; step 2"
        assert slot["repograph_symbols"] == ["a.b", "c.d"]

    def test_reseeding_fills_only_when_task_description_empty(
        self, workspace: Path
    ) -> None:
        """If the existing task_description is empty, the seed fills it."""
        update_sidecar(
            workspace=workspace,
            session_id="sess-1",
            fields={"task_description": "", "plan": "some plan"},
        )
        seed_sidecar(
            workspace=workspace,
            session_id="sess-1",
            task_description="filled in",
        )
        slot = json.loads(sidecar_path(workspace).read_text())["sess-1"]
        assert slot["task_description"] == "filled in"
        assert slot["plan"] == "some plan"

    def test_empty_session_id_returns_none(self, workspace: Path) -> None:
        result = seed_sidecar(
            workspace=workspace, session_id="", task_description="x"
        )
        assert result is None
        assert not sidecar_path(workspace).exists()

    def test_missing_workspace_dir_is_created(self, tmp_path: Path) -> None:
        """A workspace path that doesn't exist yet is still handled."""
        ws = tmp_path / "not-yet-existing"
        result = seed_sidecar(
            workspace=ws, session_id="sess-1", task_description="x"
        )
        assert result is not None
        assert ws.is_dir()

    def test_ioerror_returns_none_silently(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A permissions/disk error must NOT raise out to the caller."""
        # Make the state dir unwritable.
        state_dir = workspace / ".forge-oh"
        state_dir.mkdir()
        # 0o555 = read+execute only; can't create files.
        state_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = seed_sidecar(
                workspace=workspace,
                session_id="sess-1",
                task_description="x",
            )
            assert result is None
        finally:
            # Restore so pytest can clean up.
            state_dir.chmod(stat.S_IRWXU)

    def test_corrupt_sidecar_is_recreated(self, workspace: Path) -> None:
        """A pre-existing garbage file must not brick the seeder."""
        path = sidecar_path(workspace)
        path.parent.mkdir(parents=True)
        path.write_text("{{ this is not valid JSON")
        seed_sidecar(
            workspace=workspace,
            session_id="sess-1",
            task_description="fresh start",
        )
        payload = json.loads(path.read_text())
        assert payload["sess-1"]["task_description"] == "fresh start"

    def test_atomic_write_leaves_no_temp_file(self, workspace: Path) -> None:
        """After a seed, no ``.tmp`` file is left behind.

        The persistent ``.lock`` sibling IS expected — it is what serializes
        concurrent writers across workers. See :func:`_rmw` for why we
        deliberately don't unlink it.
        """
        seed_sidecar(
            workspace=workspace, session_id="sess-1", task_description="x"
        )
        state_dir = workspace / ".forge-oh"
        for entry in state_dir.iterdir():
            assert not entry.name.endswith(".tmp") and ".tmp." not in entry.name, (
                f"leftover tmp file: {entry}"
            )


class TestUpdateSidecar:
    def test_merges_into_existing_slot(self, workspace: Path) -> None:
        seed_sidecar(
            workspace=workspace, session_id="sess-1", task_description="X"
        )
        update_sidecar(
            workspace=workspace,
            session_id="sess-1",
            fields={"plan": "step 1", "symptom": "TypeError"},
        )
        slot = json.loads(sidecar_path(workspace).read_text())["sess-1"]
        assert slot["task_description"] == "X"
        assert slot["plan"] == "step 1"
        assert slot["symptom"] == "TypeError"

    def test_empty_fields_returns_none(self, workspace: Path) -> None:
        assert update_sidecar(
            workspace=workspace, session_id="sess-1", fields={}
        ) is None

    def test_non_serializable_field_dropped_without_raise(
        self, workspace: Path
    ) -> None:
        class NotJson:
            pass

        result = update_sidecar(
            workspace=workspace,
            session_id="sess-1",
            fields={"bad": NotJson()},  # type: ignore[dict-item]
        )
        assert result is None
        # No sidecar was written because the payload was rejected up front.
        assert not sidecar_path(workspace).exists()

    def test_empty_string_value_is_respected(self, workspace: Path) -> None:
        """update_sidecar honors explicit empty-string clears."""
        update_sidecar(
            workspace=workspace,
            session_id="sess-1",
            fields={"symptom": "TypeError"},
        )
        update_sidecar(
            workspace=workspace,
            session_id="sess-1",
            fields={"symptom": ""},
        )
        slot = json.loads(sidecar_path(workspace).read_text())["sess-1"]
        assert slot["symptom"] == ""

    def test_empty_session_id_returns_none(self, workspace: Path) -> None:
        assert (
            update_sidecar(
                workspace=workspace, session_id="", fields={"plan": "x"}
            )
            is None
        )

    def test_concurrent_updates_serialize(self, workspace: Path) -> None:
        """Two writers on distinct sessions must not corrupt the file."""
        def _writer(i: int) -> None:
            update_sidecar(
                workspace=workspace,
                session_id=f"sess-{i}",
                fields={"task_description": f"task {i}"},
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(_writer, range(16)))

        payload = json.loads(sidecar_path(workspace).read_text())
        # All 16 sessions landed with their correct task_description.
        assert len(payload) == 16
        for i in range(16):
            assert payload[f"sess-{i}"]["task_description"] == f"task {i}"


class TestContractWithHook:
    """Round-trip: what the seeder writes, the hook can load."""

    def test_hook_loader_reads_seeded_task_description(
        self, workspace: Path
    ) -> None:
        # Import lazily so the BFF unit suite doesn't require the tools_ext
        # package at collection time.
        pytest.importorskip("openhands_tools_ext.trajectory.hook")
        from openhands_tools_ext.trajectory import hook as hook_mod

        seed_sidecar(
            workspace=workspace,
            session_id="sess-abc",
            task_description="ship slice F.12",
        )
        slot = hook_mod._load_sidecar(workspace, "sess-abc")
        assert slot["task_description"] == "ship slice F.12"
