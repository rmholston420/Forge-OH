"""Patch-apply + test-run stage of the F.3 harness.

DELIBERATELY STUBBED in this commit. Docker glue lands in a follow-up slice
after we can inspect the swebench image layout on Colossus. The stubs raise
`NotImplementedError` with the exact next step, so the dry-run script
`bench_pathF_swebench.py --dry-plan-only` still exercises everything else
(task load, oracle prompt, vLLM call, JSON emit) end-to-end.

Follow-up slice will implement:
1. `docker pull swebench/sweb.eval.x86_64.<instance_id>:latest`
2. `docker run -d --name foh-eval-<run_id> <image> sleep infinity`
3. `docker cp` the model's patch into the container
4. `docker exec ... git apply` the patch inside `/testbed`
5. `docker exec ... <FAIL_TO_PASS test command>` + capture output
6. `docker exec ... <PASS_TO_PASS test command>` + capture output
7. Parse pytest output to determine resolved=true/false
8. `docker rm -f foh-eval-<run_id>` unless --keep-sandbox

References for the follow-up slice:
- SWE-bench harness source: princeton-nlp/SWE-bench @ main :: harness/context_manager.py
- Image naming: swebench/sweb.eval.x86_64.<instance_id>:latest (verified against DockerHub)
"""
from __future__ import annotations

from dataclasses import dataclass


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
        "For now, run with --dry-plan-only to exercise task load + prompt + vLLM without docker."
    )
