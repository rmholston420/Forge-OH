# Forge-OH Session Handoff — 2026-08-05 20:20 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 1 COMPLETE + F.3 SWE-bench Verified validation CLOSED. Stage 2 (Inference-Backend Flexibility) not yet started.
- **Plugin / kernel component:** kernel · BFF · model_router.
- **Port(s) in progress:** none. Next port: `InferenceBackend` protocol (Stage 2.1).

## Completed this session

- **F.3 Path A SWE-bench Verified full-500 run** on green Stage-1 main (`530db1a`):
  - **pass@1 = 26.6%** (133/500 raw) · **28.6%** attempted-only (133/465 excl. 35 context-skips)
  - Wall total 8h55m · median/task 5.52s · mean/task 10.86s
  - Zero harness crashes · zero vLLM disconnects · zero docker apply failures
  - GPU envelope stable: 32,599 MiB peak VRAM (99.98%) · 75 °C peak temp · 454 W peak power · 89% avg util · 464/500 NVML sample sessions
  - Artifacts: `~/.forge-oh/bench_pathF_swebench/20260805_1025_run/` (Colossus-local, gitignored per ADR-016)
- **c01 canonical coder ratification (F.1b) CONFIRMED.** F.3 full-500 produced no signal to re-select or swap; c01 stays canonical.
- **Per-repo verdict**: scikit-learn/pytest/xarray strong (37-53% attempted); astropy/matplotlib weak (9-16% raw); django (N=231) most defensible at 28.1% raw.
- **ADR-013 amendment #2** prepended documenting the F.3 full-500 verdict, GPU envelope, per-repo breakdown, and CLOSED status for F.3 Path A validation phase.
- **BUILD_LOG.md** appended with F.3 full-500 completion entry.
- **KNOWN_ISSUES.md** gained informational entry documenting 7.0% context-budget-skip ceiling as c01 upper bound at `max_model_len=32768`.
- **ADR index (`docs/adr/README.md`)** row for ADR-013 updated with amendment #2 status.

## Remaining before current Definition of Done

- **Stage 1 DoD:** none — Stage 1 is fully complete AND validated by full-500 SWE-bench Verified run.
- **Stage 2 DoD:** all of Stage 2 remains. Next action below.
- **F.3 follow-up (deferred, not blocking):** implement `apply_and_test.py` docker glue (8-step reference in module docstring). Not required for Stage 2 progression.
- **ADR-013 amendment #3 (queued, not blocking):** will land if/when Path B (Stage 1H.5 full Forge-OH agent loop) produces a materially different pass@1.

## Open questions / awaiting user answer

- None. F.3 Path A validation phase closed cleanly with the full-500 verdict. Two Stage-2 exit-gate items already filed in `KNOWN_ISSUES.md` (agent-preset `ModelId` static Literal · `agentPresetId null` on runs) resolve together in Stage 2.1.

## Exact next action

Begin **Stage 2.1: `InferenceBackend` protocol in `bff/services/model_router.py`**, per `docs/reconciliation-plan-v1.md` Stage 2. Scope:

- Introduce `InferenceBackend` protocol mapping `ModelId → {endpoint, api_style, sampling_defaults}`.
- Wire the two Colossus vLLM endpoints (`:8501` coder, `:8511` planner) and Ollama (`:11434`) into the resolver.
- Update agent-preset seed data so at least one preset resolves to c01 canonical coder locally.
- Persist `agentPresetId` on run records (resolves the `agentPresetId: null` KNOWN_ISSUES entry).
- Exit-gate: creating a preset with a real local model produces a `routing.model` matching that preset on the resulting run record.

Colossus is on `main` at `530db1a` before this closeout commit lands; working tree clean; F.3 artifacts preserved at `~/.forge-oh/bench_pathF_swebench/20260805_1025_run/`.
