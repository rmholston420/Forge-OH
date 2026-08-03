"""Tests for the run-completion hook (Slice F.5b)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from openhands_tools_ext.trajectory import hook as hook_mod
from openhands_tools_ext.trajectory.schema import (
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore


def _stdin(monkeypatch: pytest.MonkeyPatch, payload: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))


def _write_verify_state(workspace: Path, session_id: str, state: dict[str, object]) -> None:
    state_dir = workspace / hook_mod.STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / hook_mod.VERIFY_STATE_FILE).write_text(json.dumps({session_id: state}))


def _write_sidecar(workspace: Path, session_id: str, payload: dict[str, object]) -> None:
    state_dir = workspace / hook_mod.STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / hook_mod.TRAJECTORY_SIDECAR_FILE).write_text(json.dumps({session_id: payload}))


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("OPENHANDS_SESSION_ID", "sess_1")
    # Force the store to write into the workspace-scoped path (not
    # the developer's real ~/.forge-oh).
    monkeypatch.setenv(
        "FORGE_OH_TRAJECTORY_DB", str(tmp_path / hook_mod.STATE_DIR / "trajectories.db")
    )
    monkeypatch.delenv("FORGE_OH_TRAJECTORY_INDEX_INLINE", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


class TestHookCLI:
    def test_empty_stdin_returns_nonzero(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _stdin(monkeypatch, "")
        assert hook_mod.main() == 1
        assert "empty stdin" in capsys.readouterr().err

    def test_bad_json_returns_nonzero(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _stdin(monkeypatch, "not json {{{")
        assert hook_mod.main() == 1
        assert "bad JSON" in capsys.readouterr().err

    def test_non_object_stdin_rejected(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _stdin(monkeypatch, "[1, 2, 3]")
        assert hook_mod.main() == 1
        assert "must be an object" in capsys.readouterr().err

    def test_non_stop_event_is_noop(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _stdin(monkeypatch, json.dumps({"event_type": "PreToolUse"}))
        assert hook_mod.main() == 0
        body = json.loads(capsys.readouterr().out)
        assert "non-STOP" in body["reason"]

    def test_missing_project_dir_returns_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
        monkeypatch.delenv("OPENHANDS_WORKING_DIR", raising=False)
        _stdin(monkeypatch, json.dumps({"event_type": "Stop"}))
        assert hook_mod.main() == 1
        assert "OPENHANDS_PROJECT_DIR" in capsys.readouterr().err

    def test_missing_session_id_returns_nonzero(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("OPENHANDS_SESSION_ID", raising=False)
        _stdin(monkeypatch, json.dumps({"event_type": "Stop"}))
        assert hook_mod.main() == 1
        assert "session id" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Source assembly
# ---------------------------------------------------------------------------


class TestBuildSummaryFromSources:
    def test_all_empty_yields_unknown_status(self, workspace: Path) -> None:
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace,
            session_id="sess_1",
            run_id="run_1",
        )
        assert summary.run_id == "run_1"
        assert summary.session_id == "sess_1"
        assert summary.task_description == ""
        assert summary.final_status == TrajectoryStatus.UNKNOWN

    def test_env_task_used_when_sidecar_missing(self, workspace: Path) -> None:
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace,
            session_id="sess_1",
            run_id="run_1",
            env_task="fix null deref",
        )
        assert summary.task_description == "fix null deref"

    def test_verify_state_maps_to_success(self, workspace: Path) -> None:
        _write_verify_state(workspace, "sess_1", {"last_verdict": "pass"})
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace, session_id="sess_1", run_id="run_1"
        )
        assert summary.final_status == TrajectoryStatus.SUCCESS

    def test_verify_state_maps_fail_to_failed(self, workspace: Path) -> None:
        _write_verify_state(workspace, "sess_1", {"last_verdict": "fail"})
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace, session_id="sess_1", run_id="run_1"
        )
        assert summary.final_status == TrajectoryStatus.FAILED

    def test_unknown_verdict_maps_to_unknown(self, workspace: Path) -> None:
        _write_verify_state(workspace, "sess_1", {"last_verdict": "banana"})
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace, session_id="sess_1", run_id="run_1"
        )
        assert summary.final_status == TrajectoryStatus.UNKNOWN

    def test_sidecar_populates_signal_fields(self, workspace: Path) -> None:
        _write_sidecar(
            workspace,
            "sess_1",
            {
                "task_description": "fix null deref",
                "plan": "1. reproduce\n2. patch",
                "symptom": "AttributeError",
                "repograph_repo_key": "repo_main",
                "repograph_symbols": ["a.func", "b.Class.method"],
                "diffs": [
                    {"path": "a.py", "lines_added": 3, "lines_removed": 1, "summary": ""},
                ],
            },
        )
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace, session_id="sess_1", run_id="run_1"
        )
        assert summary.task_description == "fix null deref"
        assert summary.plan.startswith("1. reproduce")
        assert summary.symptom == "AttributeError"
        assert summary.repograph_repo_key == "repo_main"
        assert summary.repograph_symbols == ["a.func", "b.Class.method"]
        assert len(summary.diffs) == 1
        assert summary.diffs[0].path == "a.py"

    def test_sidecar_task_takes_precedence_over_env(self, workspace: Path) -> None:
        _write_sidecar(workspace, "sess_1", {"task_description": "sidecar wins"})
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace,
            session_id="sess_1",
            run_id="run_1",
            env_task="env task",
        )
        assert summary.task_description == "sidecar wins"

    def test_malformed_diff_entry_skipped(self, workspace: Path) -> None:
        _write_sidecar(
            workspace,
            "sess_1",
            {
                "diffs": [
                    "not a dict",
                    {"path": "ok.py", "lines_added": 1, "lines_removed": 0, "summary": ""},
                    {"missing": "required fields"},
                ]
            },
        )
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace, session_id="sess_1", run_id="run_1"
        )
        assert len(summary.diffs) == 1
        assert summary.diffs[0].path == "ok.py"

    def test_malformed_verify_state_treated_as_empty(self, workspace: Path) -> None:
        state_dir = workspace / hook_mod.STATE_DIR
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / hook_mod.VERIFY_STATE_FILE).write_text("not json {{")
        summary = hook_mod.build_summary_from_sources(
            workspace=workspace, session_id="sess_1", run_id="run_1"
        )
        assert summary.final_status == TrajectoryStatus.UNKNOWN


# ---------------------------------------------------------------------------
# End-to-end: STOP event → record persisted
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_stop_event_writes_record(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_verify_state(workspace, "sess_1", {"last_verdict": "pass"})
        _write_sidecar(
            workspace,
            "sess_1",
            {"task_description": "fix bug", "repograph_repo_key": "repo_main"},
        )
        _stdin(
            monkeypatch,
            json.dumps({"event_type": "Stop", "run_id": "run_1"}),
        )
        assert hook_mod.main() == 0
        body = json.loads(capsys.readouterr().out)
        assert body["trajectory_id"] == make_trajectory_id("run_1")
        assert body["final_status"] == "success"
        assert body["indexed"] == 0  # inline indexing not enabled

        # Persisted?
        store = TrajectoryStore()
        rec = store.get(make_trajectory_id("run_1"))
        assert rec is not None
        assert rec.task_description == "fix bug"
        assert rec.final_status == TrajectoryStatus.SUCCESS
        assert rec.embedding is None

    def test_stop_event_run_id_defaults_to_session(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _stdin(monkeypatch, json.dumps({"event_type": "Stop"}))
        assert hook_mod.main() == 0
        body = json.loads(capsys.readouterr().out)
        assert body["run_id"] == "sess_1"
        assert body["trajectory_id"] == make_trajectory_id("sess_1")

    def test_inline_indexing_populates_embedding(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Swap the default embedder for a deterministic FakeEncoder-backed one.
        from openhands_tools_ext.trajectory import embedder as embedder_mod

        class FakeEncoder:
            def encode(
                self,
                sentences: str | list[str],
                *,
                normalize_embeddings: bool = False,
                convert_to_numpy: bool = False,
            ) -> object:
                if isinstance(sentences, str):
                    return [0.5, 0.5, 0.5, 0.5]
                return [[0.5, 0.5, 0.5, 0.5] for _ in sentences]

        embedder_mod.reset_default_embedder()
        embedder_mod._DEFAULT_EMBEDDER = embedder_mod.TrajectoryEmbedder(  # type: ignore[attr-defined]
            model_name="fake", device="cpu", loader=lambda n, d: FakeEncoder()
        )
        try:
            monkeypatch.setenv("FORGE_OH_TRAJECTORY_INDEX_INLINE", "1")
            _write_sidecar(workspace, "sess_1", {"task_description": "fix bug"})
            _stdin(
                monkeypatch,
                json.dumps({"event_type": "Stop", "run_id": "run_1"}),
            )
            assert hook_mod.main() == 0
            body = json.loads(capsys.readouterr().out)
            assert body["indexed"] == 1

            store = TrajectoryStore()
            rec = store.get(make_trajectory_id("run_1"))
            assert rec is not None
            assert rec.embedding is not None
            assert rec.embedding_model == "fake"
        finally:
            embedder_mod.reset_default_embedder()

    def test_rewrite_on_second_stop_event(
        self,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # First run: FAILED.
        _write_verify_state(workspace, "sess_1", {"last_verdict": "fail"})
        _stdin(
            monkeypatch,
            json.dumps({"event_type": "Stop", "run_id": "run_1"}),
        )
        assert hook_mod.main() == 0
        capsys.readouterr()  # flush

        # Second run for same run_id: PASSED.
        _write_verify_state(workspace, "sess_1", {"last_verdict": "pass"})
        _stdin(
            monkeypatch,
            json.dumps({"event_type": "Stop", "run_id": "run_1"}),
        )
        assert hook_mod.main() == 0
        capsys.readouterr()

        store = TrajectoryStore()
        assert store.count() == 1  # replaced, not duplicated
        rec = store.get(make_trajectory_id("run_1"))
        assert rec is not None
        assert rec.final_status == TrajectoryStatus.SUCCESS
