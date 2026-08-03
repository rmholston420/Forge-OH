"""Unit tests for the VerificationStep schema."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from openhands_tools_ext.verify.schema import (
    TAIL_BYTES,
    VERIFY_STEP_TOOL_NAME,
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
    truncate_tail,
)


class TestVerificationStep:
    def test_minimal_valid_pass(self) -> None:
        step = VerificationStep(
            iteration=1,
            max_iterations=3,
            runner=VerifyRunner.PYTEST,
            duration_ms=42,
            verdict=VerifyVerdict.PASS,
        )
        assert step.iteration == 1
        assert step.max_iterations == 3
        assert step.runner == "pytest"
        assert step.verdict == "pass"
        assert step.exit_code is None
        assert step.test_selected == []
        assert step.stdout_tail == ""

    def test_full_payload_roundtrips_through_json(self) -> None:
        step = VerificationStep(
            iteration=2,
            max_iterations=3,
            runner=VerifyRunner.VITEST,
            test_selected=["src/foo.test.ts", "src/bar.test.ts"],
            command="npx vitest run src/foo.test.ts src/bar.test.ts",
            exit_code=1,
            stdout_tail="…\nFAIL src/foo.test.ts",
            stderr_tail="expected 1 to equal 2",
            duration_ms=3120,
            verdict=VerifyVerdict.FAIL,
            files_edited_since_last_verify=["/repo/src/foo.ts"],
        )
        raw = step.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["verdict"] == "fail"
        assert parsed["runner"] == "vitest"
        assert parsed["exit_code"] == 1
        rehydrated = VerificationStep.model_validate(parsed)
        assert rehydrated == step

    def test_iteration_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            VerificationStep(
                iteration=0,
                max_iterations=3,
                runner=VerifyRunner.PYTEST,
                duration_ms=0,
                verdict=VerifyVerdict.PASS,
            )

    def test_max_iterations_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            VerificationStep(
                iteration=1,
                max_iterations=0,
                runner=VerifyRunner.PYTEST,
                duration_ms=0,
                verdict=VerifyVerdict.PASS,
            )

    def test_duration_ms_cannot_be_negative(self) -> None:
        with pytest.raises(ValidationError):
            VerificationStep(
                iteration=1,
                max_iterations=1,
                runner=VerifyRunner.PYTEST,
                duration_ms=-1,
                verdict=VerifyVerdict.PASS,
            )

    def test_bad_runner_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VerificationStep(
                iteration=1,
                max_iterations=1,
                runner="cargo_test",  # type: ignore[arg-type]
                duration_ms=0,
                verdict=VerifyVerdict.PASS,
            )

    def test_bad_verdict_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VerificationStep(
                iteration=1,
                max_iterations=1,
                runner=VerifyRunner.PYTEST,
                duration_ms=0,
                verdict="maybe",  # type: ignore[arg-type]
            )


class TestTruncateTail:
    def test_short_text_unchanged(self) -> None:
        assert truncate_tail("hello") == "hello"

    def test_empty_string_returns_empty(self) -> None:
        assert truncate_tail("") == ""

    def test_long_text_truncated_from_head(self) -> None:
        head = "IGNORE " * 1000
        tail_marker = "TAILEND_TAILEND_TAILEND"
        blob = head + tail_marker
        result = truncate_tail(blob)
        assert result.startswith("…\n")
        # Tail marker must survive.
        assert tail_marker in result
        # Result must be at most TAIL_BYTES + a few bytes for the ellipsis.
        assert len(result.encode("utf-8")) <= TAIL_BYTES + 8

    def test_multibyte_boundary_does_not_crash(self) -> None:
        blob = "ä" * (TAIL_BYTES + 200)
        result = truncate_tail(blob)
        assert result.startswith("…\n")
        # No exception, non-empty.
        assert len(result) > 2


class TestConstants:
    def test_tool_name_is_verify_step(self) -> None:
        assert VERIFY_STEP_TOOL_NAME == "verify_step"


class TestFrontendParity:
    """The TS Zod schema in src/lib/schemas/verify.ts must list the same
    field names and same enum values as the Python model."""

    TS_PATH = Path(__file__).resolve().parents[3] / "src" / "lib" / "schemas" / "verify.ts"

    def test_ts_file_exists(self) -> None:
        assert self.TS_PATH.exists(), f"missing {self.TS_PATH}"

    def test_ts_field_names_match_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        for field in VerificationStep.model_fields:
            # Every python field must appear as a key in the zod object.
            assert re.search(rf"\b{field}:\s", ts_source), (
                f"field '{field}' missing from src/lib/schemas/verify.ts"
            )

    def test_ts_verdict_enum_matches_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        for verdict in VerifyVerdict:
            assert f"'{verdict.value}'" in ts_source, (
                f"verdict '{verdict.value}' missing from TS enum"
            )

    def test_ts_runner_enum_matches_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        for runner in VerifyRunner:
            assert f"'{runner.value}'" in ts_source, f"runner '{runner.value}' missing from TS enum"

    def test_ts_tool_name_matches_python(self) -> None:
        ts_source = self.TS_PATH.read_text()
        assert f"'{VERIFY_STEP_TOOL_NAME}'" in ts_source, (
            "VERIFY_STEP_TOOL_NAME constant missing or mismatched in TS"
        )
