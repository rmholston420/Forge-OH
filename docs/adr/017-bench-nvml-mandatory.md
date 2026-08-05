# ADR-017 — NVML GPU sampling mandatory on every bench harness

**Status:** Ratified
**Lock-in phase:** Cross-cutting (applies to every bench harness in `bench/`)
**Supersedes:** —
**Related:** ADR-013 (Qwen3.6-27B canonical coder/planner), F.1b (first NVML sampler), F.3 Path A (first application of this rule)

## Context

The F.1b instrumented rebench (2026-08-03) added an NVML background sampler
that captured `gpu_util`, `vram_used`, `gpu_temp`, and `power_draw` around
every vLLM inference call. That work was retained as
`bench/pathF_instrumented/nvml_sampler.py` with an explicit note in its module
docstring: **"All future bench runs must use this sampler."**

The F.3 SWE-bench Verified harness (`bench/pathF_swebench/`) shipped its first
docker-real run (2026-08-05 07:05 EDT, `django__django-10914`, resolved) without
GPU instrumentation. That would have made speed/quality reporting on a full
500-task run uninterpretable: tok/s alone cannot distinguish a well-provisioned
run from one that was thermally throttled, VRAM-pressured, or contending with
another CUDA workload.

The user's standing instruction — captured verbatim in the F.3 conversation on
2026-08-05 07:10 EDT — is:

> "these benchmarking tests, and all such tests, always need to track our GPU metrics"

This ADR codifies that instruction as a permanent bench-harness rule.

## Decision

Every bench harness under `bench/` **must** wrap the workload of interest in an
`NVML GpuSampler` window and persist the resulting stats to per-task JSON.

Canonical location: `bench/_common/nvml_sampler.py` (promoted 2026-08-05).
A compatibility shim remains at `bench/pathF_instrumented/nvml_sampler.py` so
the F.1b harness continues to work unchanged.

Concrete requirements:

1. **Import**: `from bench._common.nvml_sampler import GpuSampler`
2. **Sampling cadence**: `interval_s=0.5` (matches F.1b; ~2 Hz).
3. **Per-task record**: every task JSON contains a `gpu_inference` field with
   the sampler's `to_dict()` output. Harnesses whose workload has a distinct
   post-inference phase (e.g. F.3 docker apply-and-test) also record
   `gpu_harness` for that phase.
4. **Run-level aggregate**: `summary.json` contains a `gpu` block with
   cross-task `avg` and `max` for VRAM, temperature, power, and GPU utilization.
5. **Graceful degrade**: if `pynvml` is not importable, sampling records
   `{"samples": 0, "nvml_available": false, ...}` per task and the harness
   still runs. The harness must not hard-fail on missing NVML.
6. **No sampler-only benchmarks**: a run whose summary reports `"gpu": null`
   for a Colossus target is a bug and must be treated as such.

## Rationale

- **Interpretability.** Quality + tok/s + wall clock without GPU state is
  unfalsifiable: a slow run could be model, docker, disk, contention, or
  throttling. NVML directly answers which.
- **Regression detection.** VRAM/temperature drift across runs of the same
  cell signals a coexistence problem (planner still up, hidden CUDA process,
  cooling issue) before it corrupts a full 500-task pass@1 number.
- **Single canonical location.** Duplicating the sampler under each
  `bench/pathX_*/` directory would drift (F.1b already had it; F.3 would have
  been the second copy). One canonical location, one import path.
- **Preserves F.1b history.** F.1b's harness references
  `bench/pathF_instrumented/nvml_sampler.py` via a sibling-directory
  `sys.path.insert(0, ...)` + `from nvml_sampler import GpuSampler` pattern.
  The compat shim re-exports from `bench._common.nvml_sampler` so no F.1b
  code needed to change.

## Alternatives considered

1. **Leave the sampler under `bench/pathF_instrumented/` and import from there.**
   Rejected: F.3 is not the last bench. Every future harness would need to
   know the sampler lives inside an unrelated path.
2. **Copy the sampler into each bench dir.** Rejected: two copies drift within
   weeks. This is exactly the vendor-first anti-pattern ADR-016 flagged for
   `scripts/`.
3. **Sample only for cells with vLLM, skip for docker/CPU-only phases.**
   Rejected: the docker window is where VRAM contention with a background
   planner would show up. Sampling it explicitly (as a separate window with
   its own field name) IS the diagnostic. Sampling overhead is negligible.

## Consequences

Files that change on adoption:

- `bench/_common/__init__.py` — new (empty).
- `bench/_common/nvml_sampler.py` — new (moved from
  `bench/pathF_instrumented/nvml_sampler.py`; content unchanged).
- `bench/pathF_instrumented/nvml_sampler.py` — replaced with re-export shim.
- `bench/pathF_swebench/bench_pathF_swebench.py` — wired `GpuSampler` around
  `call_model()` (`gpu_inference`) and around `apply_patch_and_run_tests()`
  (`gpu_harness`); per-task JSON gains `gpu_inference` + `gpu_harness`;
  `summary.json` gains `gpu` block.
- `docs/adr/README.md` — index entry for ADR-017.
- Every future bench harness — same integration pattern.

Files that do **not** need to change:

- `bench/pathF_instrumented/bench_pathF.py` — the shim keeps its
  `from nvml_sampler import GpuSampler` import working.

## Lock-in phase

Cross-cutting. Enforced on every bench harness from 2026-08-05 forward. The
first application is F.3 Path A (SWE-bench Verified `smoke-25` + full-500 runs
against ADR-013's ratified coder c01).

## References

- Original sampler module docstring: `bench/pathF_instrumented/nvml_sampler.py`
  → now `bench/_common/nvml_sampler.py`
- F.1b harness usage: `bench/pathF_instrumented/bench_pathF.py`
- User instruction, 2026-08-05 07:10 EDT: "these benchmarking tests, and all
  such tests, always need to track our GPU metrics"
- ADR-013 (coder/planner selection — the runs this ADR gates)
