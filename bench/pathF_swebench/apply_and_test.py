"""Patch-apply + test-run stage of the F.3 harness.

Two responsibilities:

1. `normalize_patch(text)` — strip markdown code fences that some models
   (c01 confirmed via F.3.0 dry-run 2026-08-05 06:53 EDT on
   django__django-10914) wrap around unified diffs. `git apply` rejects
   fenced text.

2. `apply_patch_and_run_tests(instance_id, patch, model_name, artifacts_root)`
   — shells out to the official SWE-bench harness
   (`python -m swebench.harness.run_evaluation`) with a single-instance
   predictions.jsonl. Reads the per-instance report and returns resolved
   True/False plus captured stdout/stderr.

Design rationale (see BUILD_LOG 2026-08-05 06:55 EDT):
- Reuse the official harness — it maintains per-repo test-invocation quirks
  (each SWE-bench task has repo-specific pytest incantations).
- Rolling our own docker pull + git apply + pytest parser would be ~150
  fragile lines that duplicate what the harness already does correctly.
- The harness is `pip install swebench` (Python ≥3.10). Confirmed against
  SWE-bench GitHub main branch pyproject.toml on 2026-08-05.

Predictions.jsonl schema (verified against harness source
`swebench/harness/run_evaluation.py`):
    {
      "instance_id": "<instance>",
      "model_name_or_path": "<name>",
      "model_patch": "<unified diff>"
    }
    one JSON object per line, `\\n`-terminated.

Result-file location (verified against harness source):
    <run_cwd>/logs/run_evaluation/<run_id>/<model_slug>/<instance_id>/report.json
    with schema {instance_id: {"resolved": bool, ...}}
    model_slug = model_name.replace("/", "__")

Artifacts layout (this module):
    <artifacts_root>/<run_id>/
      predictions.jsonl
      logs/                      (harness-managed)
      evaluation_results/        (harness-managed)
      harness_stdout.log
      harness_stderr.log

Failure modes handled:
- swebench not importable → RuntimeError with install hint.
- Empty/None patch → resolved=False, error="empty patch".
- Harness subprocess non-zero exit → resolved=False, error captured.
- Report file missing after harness exit → resolved=False,
  error="no report; likely image pull failure".
- Report has no `resolved` key → resolved=False, error="report shape unexpected".
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# --- fence stripper --------------------------------------------------------

_FENCE_OPEN_RE = re.compile(r"^\s*```(?:diff|patch)?\s*\n", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"\n\s*```\s*$")


def normalize_patch(text: str) -> str:
    """Strip markdown code fences and outer whitespace from model output.

    Handles:
    - Fully-wrapped: ``` ... ``` / ```diff ... ``` / ```patch ... ```
    - Extra leading/trailing whitespace
    - Trailing prose after the diff — LEFT IN PLACE (git apply will fail
      loudly, which is what we want for scoring — silently swallowing prose
      would mask a bad model output).
    """
    if not text:
        return text
    stripped = text.strip()
    stripped = _FENCE_OPEN_RE.sub("", stripped, count=1)
    stripped = _FENCE_CLOSE_RE.sub("", stripped, count=1)
    return stripped.strip()


# --- docker apply + test ---------------------------------------------------

@dataclass
class TestResult:
    resolved: bool
    stdout_tail: str = ""
    stderr_tail: str = ""
    report: dict = field(default_factory=dict)
    error: str | None = None
    harness_return_code: int | None = None


def _slug(model_name: str) -> str:
    """SWE-bench harness slug rule: replace '/' with '__' for path safety."""
    return model_name.replace("/", "__")


def _tail(s: str, n: int = 4000) -> str:
    if s is None:
        return ""
    return s if len(s) <= n else s[-n:]


def _swebench_available() -> tuple[bool, str]:
    """Confirm the harness is importable + CLI reachable. Returns (ok, hint)."""
    try:
        import swebench  # noqa: F401
    except ImportError:
        return False, (
            "swebench not installed. Install into the same interpreter as "
            "this script: `pip install swebench` (needs Python >= 3.10)."
        )
    # Try `python -m swebench.harness.run_evaluation --help` — cheap sanity.
    try:
        r = subprocess.run(
            [sys.executable, "-m", "swebench.harness.run_evaluation", "--help"],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "swebench CLI hung on --help (>30s); investigate the install."
    if r.returncode != 0:
        return False, (
            f"swebench CLI exited {r.returncode} on --help. stderr tail:\n"
            f"{_tail(r.stderr, 800)}"
        )
    return True, ""


def apply_patch_and_run_tests(
    instance_id: str,
    patch: str,
    model_name: str,
    artifacts_root: Path,
    run_id: str,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
    max_workers: int = 1,
    timeout_seconds: int = 1800,
    keep_sandbox: bool = False,
) -> TestResult:
    """Run one prediction through the official SWE-bench harness.

    Args:
        instance_id: SWE-bench Verified instance id, e.g. "django__django-10914".
        patch: unified diff text (must already be fence-stripped via
            `normalize_patch`).
        model_name: identifier used in report paths, e.g.
            "c01_coder_vllm_qwen36_27b_int4".
        artifacts_root: parent directory for this run's outputs. Will contain
            `<artifacts_root>/<run_id>/predictions.jsonl` plus harness-managed
            `logs/` and `evaluation_results/` subdirs.
        run_id: string used by the harness for its own directory naming.
        dataset_name: HF dataset id. Defaults to Verified.
        split: HF dataset split. Defaults to "test".
        max_workers: harness parallelism. F.3.0 single-task = 1.
        timeout_seconds: hard cap on the whole harness invocation.
        keep_sandbox: harness passes `--cache_level` env by default, which
            keeps images and containers around. If False (default), we still
            leave them — cleaning up midway breaks concurrent runs. Reserved
            for future cleanup hooks.
    """
    if not patch or not patch.strip():
        return TestResult(
            resolved=False,
            error="empty patch; model produced no output",
        )

    ok, hint = _swebench_available()
    if not ok:
        return TestResult(resolved=False, error=hint)

    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    pred_line = json.dumps(
        {
            "instance_id": instance_id,
            "model_name_or_path": model_name,
            "model_patch": patch,
        },
        ensure_ascii=False,
    )
    pred_path = run_dir / "predictions.jsonl"
    pred_path.write_text(pred_line + "\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", dataset_name,
        "--split", split,
        "--predictions_path", str(pred_path),
        "--run_id", run_id,
        "--instance_ids", instance_id,
        "--max_workers", str(max_workers),
    ]

    stdout_log = run_dir / "harness_stdout.log"
    stderr_log = run_dir / "harness_stderr.log"

    try:
        r = subprocess.run(
            cmd,
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as te:
        stdout_log.write_text(te.stdout or "", encoding="utf-8")
        stderr_log.write_text(te.stderr or "", encoding="utf-8")
        return TestResult(
            resolved=False,
            stdout_tail=_tail(te.stdout or ""),
            stderr_tail=_tail(te.stderr or ""),
            error=f"harness timeout after {timeout_seconds}s",
            harness_return_code=None,
        )

    stdout_log.write_text(r.stdout or "", encoding="utf-8")
    stderr_log.write_text(r.stderr or "", encoding="utf-8")

    slug = _slug(model_name)
    report_path = (
        run_dir / "logs" / "run_evaluation" / run_id / slug
        / instance_id / "report.json"
    )

    if not report_path.exists():
        return TestResult(
            resolved=False,
            stdout_tail=_tail(r.stdout or ""),
            stderr_tail=_tail(r.stderr or ""),
            error=(
                f"harness produced no report at {report_path}. "
                "Common causes: docker image pull failure, patch failed to "
                "apply, harness aborted before per-instance execution."
            ),
            harness_return_code=r.returncode,
        )

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as je:
        return TestResult(
            resolved=False,
            stdout_tail=_tail(r.stdout or ""),
            stderr_tail=_tail(r.stderr or ""),
            error=f"report.json unreadable: {je}",
            harness_return_code=r.returncode,
        )

    inst = report.get(instance_id, {})
    if "resolved" not in inst:
        return TestResult(
            resolved=False,
            stdout_tail=_tail(r.stdout or ""),
            stderr_tail=_tail(r.stderr or ""),
            report=report,
            error="report shape unexpected: no 'resolved' key",
            harness_return_code=r.returncode,
        )

    return TestResult(
        resolved=bool(inst["resolved"]),
        stdout_tail=_tail(r.stdout or ""),
        stderr_tail=_tail(r.stderr or ""),
        report=report,
        harness_return_code=r.returncode,
    )
