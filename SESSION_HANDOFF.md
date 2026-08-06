# Forge-OH Session Handoff — 2026-08-05 21:58 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 2 (Inference-Backend Flexibility) — plan amended, code not yet started.
- **Plugin / kernel component:** kernel · BFF · `model_router` + new `bff/services/inference_backends/` package.
- **Port(s) in progress:** `InferenceBackend` protocol (Stage 2.1). Additive to existing role-routing core; supervisor + `RoleRoute` semantics preserved.

## Completed this session

- **Reality check + plan amendment:** discovered the v1 first-draft Stage 2 was authored against an older `model_router.py` snapshot (single vLLM, Ollama-only, `route_by_role(role, model, backend_id)` rewrite). The live router (post-F.3, `main`) implements ADR-009 §3a dual-role topology with `ops/vllm_supervisor.sh` swap-on-demand, `RoleRoute` dataclass, per-role locks, VLLM_SUPERVISOR_REQUEST_CAP (G.1 fix), and Ollama-fallback semantics. Executing v1 verbatim would have deleted all of that.
- **Amended plan committed:** `docs/reconciliation-plan-stage-2.md` (canonical, 957 lines) + `docs/reconciliation-plan-v1.md` Stage 2 section rewritten as a short summary + pointer. Full reality-delta table at the bottom of the stage-2 doc.
- **Core invariant recorded:** `InferenceBackend` is a health-inventory + selection layer ABOVE `route_by_role()`, not a replacement. `route_by_role()` gains only an optional `backend_id: str | None = None` parameter; default (None) preserves existing behavior byte-for-byte.
- **Adapter set finalized as six** (not the v1 first draft's four): `ollama`, `vllm-coder` (:8501), `vllm-planner` (:8511), `vllm-legacy` (:8500, probe-only), `llamacpp` (health visibility only until Colossus deploys it), `sglang` (same).
- **KNOWN_ISSUES folded in:** the two Stage-2-adjacent items (AgentPreset `Literal` cloud-only; `agentPresetId: null` on runs) become 2.1.7 and 2.1.8 in the amended plan.
- **BUILD_LOG.md appended** with a plan-amendment entry documenting the reality delta and rationale.

## Remaining before current Definition of Done

Amended Stage 2 Definition of Done, ordered:

1. **Stage 2.1 (backend health-inventory layer + `route_by_role` additive extension + AgentPreset widening + `agentPresetId` end-to-end):** `bff/services/inference_backends/` package with six adapters, registry, protocol, types; `GET /api/inference-backends`; `POST /runs` accepts optional `backendId`; `AgentPreset.model` widened from cloud `Literal` to free-form string with new `backendId` + `role` fields; three seeded presets (ap-1 coder canonical, ap-2 planner, ap-3 Ollama fallback); `agentPresetId` surfaced on `GET /runs/{id}`.
2. **Stage 2.2 (frontend selector + live health):** `HealthBadge` reusing existing `badge badge--*` CSS classes (NOT Tailwind bg-*); `BackendSelector` radio group; wired into Agent Presets editor + run-creation form.
3. **Stage 2.3 (docs-only):** `docs/colossus-inference-setup.md` with SM_120 flag matrix. No new builds on Colossus.
4. **Stage 2.4 (VRAM-aware quant + concurrency):** `hardware.py`, `quant_selector.py`, `concurrency.py`, `GET /api/inference-backends/concurrency-limit`, `ConcurrencyLimitDisplay` on Settings.
5. **Exit gate:** full manual checklist in `docs/reconciliation-plan-stage-2.md` § "Stage 2 exit gate", including an F.3 SWE-bench 5-task smoke re-run to confirm additive `backendId` did not regress role-based routing (must land inside the smoke-30 v2 regression band: 22–38% raw).

## Open questions / awaiting user answer

- **AgentPreset SQLite persistence** (Stage 1.5 leftover): keeping `_PRESETS` in-memory for Stage 2 exit; deferred to a Stage 3 leftover slot. Not blocking Stage 2 exit gate. If a preset created via the UI must survive a BFF restart before Stage 3 lands, flag it and it becomes an in-Stage-2 addition.

## Exact next action

Execute **Stage 2.1** per `docs/reconciliation-plan-stage-2.md` § 2.1, starting at 2.0 baseline inspection on Colossus. Do NOT touch `bff/services/model_router.py` beyond appending the optional `backend_id` parameter to `route_by_role`. Do NOT delete or simplify the supervisor path, `_supervisor_ensure` locks, `_vllm_role_health`, or the Ollama fallback logic. Every code path listed under "Do NOT delete or simplify" in § 2.0 is protected by tests and ADR-009 §3a.

Colossus is on `main` at the plan-amendment commit; working tree clean.
