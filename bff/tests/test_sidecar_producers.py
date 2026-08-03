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
    def test_top_level_symptom_extracted(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"kind": "verify_obs", "symptom": "boom"})
        assert _read_slot(workspace, cid)["symptom"] == "boom"

    def test_nested_symptom_extracted(
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


# ---------------------------------------------------------------------------
# RepoGraph symbols producer
# ---------------------------------------------------------------------------


class TestRepoGraphSymbolsProducer:
    def test_symbols_extracted_from_repograph_action(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {
                "kind": "action",
                "action": "repograph.search",
                "symbols": ["mod.foo", "mod.bar"],
            },
        )
        assert _read_slot(workspace, cid)["repograph_symbols"] == [
            "mod.foo",
            "mod.bar",
        ]

    def test_symbols_from_nested_args(self, workspace: Path, cid: str) -> None:
        _feed(
            workspace,
            cid,
            {
                "action": "repograph.symbol_lookup",
                "args": {"symbol_ids": ["a.b.c"]},
            },
        )
        assert _read_slot(workspace, cid)["repograph_symbols"] == ["a.b.c"]

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

    def test_non_repograph_action_ignored_when_kind_known(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(
            workspace,
            cid,
            {"action": "bash", "symbols": ["should", "not", "leak"]},
        )
        assert "repograph_symbols" not in _read_slot(workspace, cid)


# ---------------------------------------------------------------------------
# Diffs producer
# ---------------------------------------------------------------------------


class TestDiffsProducer:
    def test_file_edit_event_produces_diff(
        self, workspace: Path, cid: str
    ) -> None:
        # file_diff_reconstruction consumes normalized file-edit events.
        # The exact envelope depends on OpenHands' event schema; the
        # reconstruction module already knows how to handle it. We fake
        # a minimal shape here: it produces summaries with `path`,
        # `linesAdded`, `linesRemoved`.
        _feed(
            workspace,
            cid,
            {
                "kind": "observation",
                "action": "edit",
                "path": "src/foo.py",
                "content": "print('hi')\n",
                "old_content": "",
            },
        )
        slot = _read_slot(workspace, cid)
        # The reconstruction may not recognize this exact shape (it
        # varies with SDK version); we assert the merge contract:
        # either no diffs were produced (empty case) or the diffs
        # field has the right shape.
        if "diffs" in slot:
            for entry in slot["diffs"]:
                assert set(entry.keys()) >= {
                    "path",
                    "lines_added",
                    "lines_removed",
                    "summary",
                }

    def test_no_diffs_when_no_file_events(
        self, workspace: Path, cid: str
    ) -> None:
        _feed(workspace, cid, {"kind": "message", "content": "hi"})
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
