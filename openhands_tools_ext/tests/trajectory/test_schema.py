"""Unit tests for the TrajectoryRecord schema (Rec #3, Slice F.1)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from openhands_tools_ext.trajectory.schema import (
    DEFAULT_RETRIEVAL_K,
    SEMANTIC_WEIGHT,
    SYMBOL_WEIGHT,
    TRAJECTORY_API_PREFIX,
    TrajectoryDiff,
    TrajectoryRecord,
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.verify.schema import (
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
)


def _minimal_record(**overrides: object) -> TrajectoryRecord:
    base: dict[str, object] = {
        "trajectory_id": "traj_run_abc",
        "run_id": "run_abc",
        "session_id": "sess_xyz",
        "task_description": "fix null deref in run_metadata_store.get",
        "final_status": TrajectoryStatus.SUCCESS,
        "created_at": "2026-08-03T12:34:56Z",
    }
    base.update(overrides)
    return TrajectoryRecord(**base)  # type: ignore[arg-type]


class TestTrajectoryRecord:
    def test_minimal_valid(self) -> None:
        rec = _minimal_record()
        assert rec.trajectory_id == "traj_run_abc"
        assert rec.run_id == "run_abc"
        assert rec.final_status == "success"
        assert rec.plan == ""
        assert rec.diffs == []
        assert rec.verify_iterations == []
        assert rec.repograph_symbols == []
        assert rec.embedding is None
        assert rec.embedding_model == ""

    def test_full_payload_roundtrips_through_json(self) -> None:
        step = VerificationStep(
            iteration=1,
            max_iterations=3,
            runner=VerifyRunner.PYTEST,
            duration_ms=42,
            verdict=VerifyVerdict.PASS,
        )
        diff = TrajectoryDiff(
            path="bff/services/run_metadata_store.py",
            lines_added=3,
            lines_removed=1,
            summary="guard against missing run_id",
        )
        rec = _minimal_record(
            plan="1. reproduce  2. patch  3. verify",
            diffs=[diff],
            verify_iterations=[step],
            symptom="AttributeError: 'NoneType' has no attribute 'run_id'",
            repograph_repo_key="6bcc20c96720",
            repograph_symbols=["bff.services.run_metadata_store.get"],
            embedding=[0.1, 0.2, 0.3],
            embedding_model="BAAI/bge-code-v1",
        )
        raw = rec.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["final_status"] == "success"
        assert parsed["diffs"][0]["path"] == "bff/services/run_metadata_store.py"
        assert parsed["verify_iterations"][0]["verdict"] == "pass"
        assert parsed["embedding"] == [0.1, 0.2, 0.3]
        rehydrated = TrajectoryRecord.model_validate(parsed)
        assert rehydrated == rec

    def test_bad_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_record(final_status="maybe")  # type: ignore[arg-type]

    def test_diff_lines_cannot_be_negative(self) -> None:
        with pytest.raises(ValidationError):
            TrajectoryDiff(path="a.py", lines_added=-1, lines_removed=0)

    def test_embedding_can_be_none(self) -> None:
        rec = _minimal_record()
        # Explicit None (writer emits, indexer fills later) must be permitted.
        rec2 = _minimal_record(embedding=None)
        assert rec.embedding is None
        assert rec2.embedding is None


class TestConstants:
    def test_api_prefix(self) -> None:
        assert TRAJECTORY_API_PREFIX == "/trajectories"

    def test_default_k(self) -> None:
        assert DEFAULT_RETRIEVAL_K == 3

    def test_weights_sum_to_one(self) -> None:
        # Co-ranking must be a convex combination.
        assert SEMANTIC_WEIGHT + SYMBOL_WEIGHT == pytest.approx(1.0)
        assert 0.0 <= SEMANTIC_WEIGHT <= 1.0
        assert 0.0 <= SYMBOL_WEIGHT <= 1.0

    def test_make_trajectory_id(self) -> None:
        assert make_trajectory_id("run_abc") == "traj_run_abc"


class TestFrontendParity:
    """The TS Zod schema in src/lib/schemas/trajectory.ts must list the
    same field names and same enum values as the Python model."""

    TS_PATH = Path(__file__).resolve().parents[3] / "src" / "lib" / "schemas" / "trajectory.ts"

    def test_ts_file_exists(self) -> None:
        assert self.TS_PATH.exists(), f"missing {self.TS_PATH}"

    def test_ts_field_names_match_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        for field in TrajectoryRecord.model_fields:
            assert re.search(rf"\b{field}:\s", ts_source), (
                f"field '{field}' missing from src/lib/schemas/trajectory.ts"
            )

    def test_ts_diff_field_names_match_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        for field in TrajectoryDiff.model_fields:
            assert re.search(rf"\b{field}:\s", ts_source), (
                f"diff field '{field}' missing from src/lib/schemas/trajectory.ts"
            )

    def test_ts_status_enum_matches_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        for status in TrajectoryStatus:
            assert f"'{status.value}'" in ts_source, f"status '{status.value}' missing from TS enum"

    def test_ts_api_prefix_matches_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        assert f"'{TRAJECTORY_API_PREFIX}'" in ts_source, (
            "TRAJECTORY_API_PREFIX constant missing or mismatched in TS"
        )
