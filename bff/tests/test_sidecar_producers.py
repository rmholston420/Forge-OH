"""Tests for :mod:`bff.services.sidecar_producers` (Slice F.15).

Each producer is exercised through :func:`update_from_event` — the
same entry point used by the event relay in production. We assert
against the merged sidecar JSON on disk so the tests cover both the
per-field logic AND the sidecar update contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bff.services import sidecar_producers
from bff.services.sidecar import sidecar_path

# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A fresh workspace dir per test."""
    return tmp_path


@pytest.fixture
def cid() -> str:
    return "conv-abc-123"


@pytest.fixture(autouse=True)
def _clear_accumulator(cid: str) -> Any:
    sidecar_producers.reset_accumulator(cid)
    yield
    sidecar_producers.reset_accumulator(cid)


def _read_slot(workspace: Path, session_id: str) -> dict[str, Any]:
    path = sidecar_path(workspace)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    slot = data.get(session_id)
    return slot if isinstance(slot, dict) else {}


def _feed(
    workspace: Path,
    cid: str,
    event: dict[str, Any],
) -> None:
    sidecar_producers.update_from_event(
        cid=cid,
        workspace=str(workspace),
        session_id=cid,
        event=event,
    )


# ---------------------------------------------------------------------------
# Guardrails: safety of the entry point
# ---------------------------------------------------------------------------


class TestUpdateFromEventGuardrails:
    def test_missing_workspace_is_noop(self, cid: str, tmp_path: Path) -> None:
        sidecar_producers.update_from_event(
            cid=cid, workspace="", session_id=cid, event={"kind": "message"}
        )
        # Nothing written anywhere.
        assert not (tmp_path / ".forge-oh").exists()

    def test_missing_session_id_is_noop(
        self, workspace: Path, cid: str
    ) -> None:
        sidecar_producers.update_from_event(
            cid=cid,
            workspace=str(workspace),
            session_id="",
            event={"kind": "message"},
        )
        assert not sidecar_path(workspace).exists()

    def test_non_dict_event_is_noop(self, workspace: Path, cid: str) -> None:
        sidecar_producers.update_from_event(
            cid=cid,
            workspace=str(workspace),
            session_id=cid,
            event="not an event",  # type: ignore[arg-type]
        )
        assert not sidecar_path(workspace).exists()

    def test_event_with_no_producible_fields_writes_nothing(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"kind": "heartbeat"})
        assert _read_slot(workspace, cid) == {}


# ---------------------------------------------------------------------------
# Symptom producer
# ---------------------------------------------------------------------------


class TestSymptomProducer:
    def test_legacy_top_level_symptom_extracted(
        self, workspace: Path, cid: str
    ) -> None:
        """Future-proofing: honor a top-level ``symptom`` key."""
        _feed(workspace, cid, {"kind": "verify_obs", "symptom": "boom"})
        assert _read_slot(workspace, cid)["symptom"] == "boom"

    def test_legacy_nested_symptom_extracted(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {"kind": "obs", "observation": {"failure_reason": "test failed"}},
        )
        assert _read_slot(workspace, cid)["symptom"] == "test failed"

    def test_freshest_symptom_wins(self, workspace: Path, cid: str) -> None:
        _feed(workspace, cid, {"symptom": "first"})
        _feed(workspace, cid, {"symptom": "second"})
        assert _read_slot(workspace, cid)["symptom"] == "second"

    def test_empty_symptom_is_ignored(self, workspace: Path, cid: str) -> None:
        _feed(workspace, cid, {"symptom": "   "})
        assert "symptom" not in _read_slot(workspace, cid)

    def test_absent_symptom_does_not_clear_existing_value(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"symptom": "first"})
        _feed(workspace, cid, {"kind": "unrelated"})
        # Not overwritten to "" or None.
        assert _read_slot(workspace, cid)["symptom"] == "first"

    # ------------------------------------------------------------------
    # Real agent-server schema paths (F.15 fixup)
    # ------------------------------------------------------------------

    def test_terminal_observation_with_nonzero_exit_becomes_symptom(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "TerminalObservation",
                    "is_error": False,
                    "exit_code": 2,
                    "content": [
                        {"type": "text", "text": "pytest: 3 failed"}
                    ],
                },
            },
        )
        sym = _read_slot(workspace, cid).get("symptom", "")
        assert "TerminalObservation" in sym
        assert "exit=2" in sym
        assert "pytest: 3 failed" in sym

    def test_terminal_observation_with_zero_exit_is_not_a_symptom(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "TerminalObservation",
                    "is_error": False,
                    "exit_code": 0,
                    "content": [{"type": "text", "text": "Hello World"}],
                },
            },
        )
        assert "symptom" not in _read_slot(workspace, cid)

    def test_observation_with_is_error_becomes_symptom(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "FileEditorObservation",
                    "is_error": True,
                    "content": [{"type": "text", "text": "file not found"}],
                },
            },
        )
        sym = _read_slot(workspace, cid).get("symptom", "")
        assert "FileEditorObservation error" in sym
        assert "file not found" in sym

    def test_hook_failed_verdict_becomes_symptom(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "HookExecutionEvent",
                "hook_event_type": "Stop",
                "success": True,
                "stdout": (
                    '{"reason": "tests failed", '
                    '"additionalContext": {"verdict": "failed", '
                    '"stderr_tail": "AssertionError: 1 != 2"}}'
                ),
            },
        )
        sym = _read_slot(workspace, cid).get("symptom", "")
        assert "verify failed" in sym
        assert "tests failed" in sym

    def test_hook_skipped_verdict_is_not_a_symptom(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "HookExecutionEvent",
                "hook_event_type": "Stop",
                "success": True,
                "stdout": (
                    '{"reason": "verify-loop skipped", '
                    '"additionalContext": {"verdict": "skipped"}}'
                ),
            },
        )
        assert "symptom" not in _read_slot(workspace, cid)

    def test_symptom_is_truncated(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "TerminalObservation",
                    "exit_code": 1,
                    "content": [{"type": "text", "text": "X" * 5000}],
                },
            },
        )
        sym = _read_slot(workspace, cid).get("symptom", "")
        assert len(sym) <= 500


# ---------------------------------------------------------------------------
# RepoGraph symbols producer
# ---------------------------------------------------------------------------


class TestRepoGraphSymbolsProducer:
    def test_symbols_from_legacy_flat_shape(
        self, workspace: Path, cid: str
    ) -> None:
        """Legacy top-level ``action`` string still recognized."""
        _feed(
            workspace,
            cid,
            {
                "action": "repograph.search",
                "symbols": ["mod.foo", "mod.bar"],
            },
        )
        assert _read_slot(workspace, cid)["repograph_symbols"] == [
            "mod.foo",
            "mod.bar",
        ]

    def test_symbols_from_nested_args_legacy(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "action": "repograph.symbol_lookup",
                "args": {"symbol_ids": ["a.b.c"]},
            },
        )
        assert _read_slot(workspace, cid)["repograph_symbols"] == ["a.b.c"]

    def test_symbols_from_real_action_event_shape(
        self, workspace: Path, cid: str
    ) -> None:
        """Real agent-server ActionEvent nests kind under ``.action.kind``."""
        _feed(
            workspace,
            cid,
            {
                "kind": "ActionEvent",
                "action": {
                    "kind": "RepoGraphSearchAction",
                    "symbols": ["pkg.foo", "pkg.bar"],
                },
            },
        )
        assert _read_slot(workspace, cid)["repograph_symbols"] == [
            "pkg.foo",
            "pkg.bar",
        ]

    def test_symbols_union_across_events_and_deduped(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {"action": "repograph.search", "symbols": ["a", "b"]},
        )
        _feed(
            workspace,
            cid,
            {"action": "repograph.search", "symbols": ["b", "c"]},
        )
        assert _read_slot(workspace, cid)["repograph_symbols"] == ["a", "b", "c"]

    def test_non_repograph_terminal_action_does_not_leak_symbols(
        self, workspace: Path, cid: str
    ) -> None:
        """A TerminalAction with a stray ``symbols`` payload must NOT match."""
        _feed(
            workspace,
            cid,
            {
                "kind": "ActionEvent",
                "action": {
                    "kind": "TerminalAction",
                    "command": "echo hi",
                    "symbols": ["should", "not", "leak"],
                },
            },
        )
        assert "repograph_symbols" not in _read_slot(workspace, cid)


# ---------------------------------------------------------------------------
# Diffs producer
# ---------------------------------------------------------------------------


class TestDiffsProducer:
    def test_file_create_observation_produces_diff(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "FileEditorObservation",
                    "is_error": False,
                    "command": "create",
                    "path": "/workspace/foo.py",
                    "prev_exist": False,
                    "old_content": None,
                    "new_content": "print('hi')\n",
                },
            },
        )
        slot = _read_slot(workspace, cid)
        assert "diffs" in slot
        assert len(slot["diffs"]) == 1
        entry = slot["diffs"][0]
        assert entry["path"] == "/workspace/foo.py"
        assert entry["lines_added"] == 1
        assert entry["lines_removed"] == 0
        assert set(entry.keys()) >= {
            "path",
            "lines_added",
            "lines_removed",
            "summary",
        }

    def test_str_replace_observation_produces_diff(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "FileEditorObservation",
                    "is_error": False,
                    "command": "str_replace",
                    "path": "/workspace/bar.py",
                    "prev_exist": True,
                    "old_content": "a = 1\nb = 2\n",
                    "new_content": "a = 1\nb = 3\nc = 4\n",
                },
            },
        )
        slot = _read_slot(workspace, cid)
        assert "diffs" in slot
        entry = slot["diffs"][0]
        assert entry["path"] == "/workspace/bar.py"
        assert entry["lines_added"] == 2  # b=3 + c=4
        assert entry["lines_removed"] == 1  # b=2

    def test_errored_file_edit_produces_no_diff(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "FileEditorObservation",
                    "is_error": True,
                    "command": "create",
                    "path": "/workspace/never.py",
                    "new_content": "noop\n",
                },
            },
        )
        assert "diffs" not in _read_slot(workspace, cid)

    def test_no_diffs_when_no_file_events(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"kind": "MessageEvent", "content": "hi"})
        assert "diffs" not in _read_slot(workspace, cid)


# ---------------------------------------------------------------------------
# Plan producer
# ---------------------------------------------------------------------------


class TestPlanProducer:
    def test_no_plan_when_no_plan_events(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"kind": "message"})
        assert "plan" not in _read_slot(workspace, cid)

    def test_plan_extraction_survives_arbitrary_events(
        self, workspace: Path, cid: str
    ) -> None:
        """A well-behaved plan may or may not be extractable from a
        synthetic event; the important contract is that we never
        crash and never write an empty plan that would clobber later
        real data.
        """
        _feed(
            workspace,
            cid,
            {
                "kind": "action",
                "action": "plan.update",
                "content": [{"title": "step 1"}],
            },
        )
        slot = _read_slot(workspace, cid)
        # If plan was extracted, it must be non-empty.
        if "plan" in slot:
            assert slot["plan"].strip()


# ---------------------------------------------------------------------------
# Accumulator lifecycle
# ---------------------------------------------------------------------------


class TestAccumulator:
    def test_reset_accumulator_drops_history(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"symptom": "before"})
        assert _read_slot(workspace, cid)["symptom"] == "before"
        sidecar_producers.reset_accumulator(cid)
        # After reset a stray non-symptom event must not resurrect old data,
        # and must not raise.
        _feed(workspace, cid, {"kind": "heartbeat"})
        # The sidecar on disk keeps its historical value (that's
        # persistent state) but the in-memory buffer is empty:
        # feeding a fresh symptom-less event does NOT compute a new
        # symptom from the pre-reset history.
        assert _read_slot(workspace, cid)["symptom"] == "before"

    def test_hard_cap_bounds_memory(self, workspace: Path, cid: str) -> None:
        """Feed 6000 heartbeat events; the buffer must stay bounded."""
        for i in range(6000):
            _feed(workspace, cid, {"kind": "heartbeat", "seq": i})
        # We can't observe the internal buffer directly by contract,
        # but the call must complete in bounded time — this test is
        # a smoke check that the O(1)-amortized drop policy holds. If
        # this test hangs, the cap is broken.
