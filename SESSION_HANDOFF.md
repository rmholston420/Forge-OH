# Forge-OH Session Handoff — 2026-08-05 09:52 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 1 COMPLETE — Stage 2 (Inference-Backend Flexibility) not yet started.
- **Plugin / kernel component:** kernel · BFF · model_router.
- **Port(s) in progress:** none. Next port: `InferenceBackend` protocol (Stage 2.1).

## Completed this session

- Three-PR chain merged to `main`:
  - PR #5 `2aa3065` — Stage 1 Reconciliation Plan v1 (sub-slices 1.1–1.7).
  - PR #6 `b37944c` — ADR-012 Dual-Mode Model Routing (docs only).
  - PR #7 `c6009c7` — F.3 SWE-bench harness + ADRs 013 / 015 / 016 / 017.
- ADR-016 mirror parity closeout committed to `main` as `c22c037`:
  - Tracked `scripts/check-approval-checkbox.ts` and `scripts/e2e-approval.ts`.
  - `.gitignore` explicit rules for `scripts/debug-out/` and `scripts/__pycache__/`.
  - Colossus-side deletion of five dead Path D bench scripts and two dead `vllm_start_qwen*` launchers superseded by `ops/vllm_launch_{coder,planner}.sh`.
- Stage 1 exit-gate: **7/7 automated + 5/5 browser eyeball + 19/19 Playwright** — all green.
- Full-500 SWE-bench Verified run killed at 20/500 (3 resolved = 15% pass@1) by user request; partial output preserved at `~/.forge-oh/bench_pathF_swebench/20260805_0907_run/`. Will be restarted clean on green Stage 1 main.

## Remaining before current Definition of Done

- **Stage 1 DoD:** none — Stage 1 is fully complete.
- **Stage 2 DoD:** all of Stage 2 remains. Next action below.

## Open questions / awaiting user answer

- **Restart full-500 SWE-bench Verified run** (was killed at 20/500 to close Stage 1 clean). User indicated intent to restart on green main.
- **Two Stage-2 exit-gate acceptance criteria** were formally deferred from Stage 1 and filed in `KNOWN_ISSUES.md`:
  - Agent-preset `ModelId` is a static `Literal` with no local-endpoint plumbing.
  - `GET /api/runs/{id}` returns `agentPresetId: null` on succeeded runs.
  These resolve together in Stage 2.1 when the `InferenceBackend` protocol formally consumes preset config.

## Exact next action

Restart the full-500 SWE-bench Verified run on green Stage 1 main. Then begin Stage 2.1: `InferenceBackend` protocol in `bff/services/model_router.py`, per `docs/reconciliation-plan-v1.md` Stage 2.

Colossus is on `main` at `c22c037` after this closeout lands; working tree clean; three stale slice branches deleted; `scripts/` inventory mirrors GitHub exactly.
