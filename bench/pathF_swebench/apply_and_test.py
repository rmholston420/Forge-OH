"""Patch-apply + test-run stage of the F.3 harness.

`normalize_patch` is live and used by the harness pre-`git apply`. It strips
markdown code fences that some models (including c01, confirmed via F.3.0 dry-run
2026-08-05 06:53 EDT on django__django-10914) wrap around unified diffs.

`apply_patch_and_run_tests` is DELIBERATELY STUBBED. Docker glue lands in a
follow-up slice after we can inspect the swebench image layout on Colossus.
The stub raises `NotImplementedError` with the exact next step, so the dry-run
script `bench_pathF_swebench.py --dry-plan-only` still exercises everything
else (task load, oracle prompt, vLLM call, patch normalization, JSON emit) end
to end.

Follow-up slice will implement:
1. `docker pull` the SWE-bench Verified sandbox image for the instance
   (canonical image naming has changed across SWE-bench releases; the
   follow-up slice resolves the correct namespace against the installed
   swebench package before pulling).
2. `docker run -d --name foh-eval-<run_id> <image> sleep infinity`
3. `docker cp` the normalized patch into the container
4. `docker exec ... git apply` the patch inside `/testbed`
5. `docker exec ... <FAIL_TO_PASS test command>` + capture output
6. `docker exec ... <PASS_TO_PASS test command>` + capture output
7. Parse pytest output to determine resolved=true/false
8. `docker rm -f foh-eval-<run_id>` unless --keep-sandbox

References for the follow-up slice:
- SWE-bench harness source: princeton-nlp/SWE-bench @ main :: harness/context_manager.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_FENCE_OPEN_RE = re.compile(r"^\s*```(?:diff|patch)?\s*\n", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"\n\s*```\s*$")


def normalize_patch(text: str) -> str:
    """Strip markdown code fences and outer whitespace from model output.

    Handles the common cases:
    - Fully-wrapped: ``` ... ``` or ```diff ... ``` or ```patch ... ```
    - Extra leading/trailing whitespace
    - Trailing prose after the diff — leaves in place (git apply will fail
      loudly, which is what we want for scoring)
    """
    if not text:
        return text
    stripped = text.strip()
    stripped = _FENCE_OPEN_RE.sub("", stripped, count=1)
    stripped = _FENCE_CLOSE_RE.sub("", stripped, count=1)
    return stripped.strip()


@dataclass
class TestResult:
    resolved: bool
    fail_to_pass_output: str
    pass_to_pass_output: str
    error: str | None = None


def apply_patch_and_run_tests(
    instance_id: str,
    patch: str,
    fail_to_pass: list[str],
    pass_to_pass: list[str],
    keep_sandbox: bool = False,
) -> TestResult:
    """Stub — see module docstring. Follow-up slice implements this."""
    raise NotImplementedError(
        "Docker apply-and-test glue lands in a follow-up slice. "
        "For now, run with --dry-plan-only to exercise task load + prompt + vLLM + patch normalization."
    )
