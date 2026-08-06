# Forge-OH Session Handoff — 2026-08-05 22:15 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 2 (Inference-Backend Flexibility) — backend layer COMPLETE, frontend layer next.
- **Plugin / kernel component:** kernel · BFF · `bff/services/inference_backends` (new package) · `bff/services/model_router.py` (additive extension only) · `bff/routers/inference_backends.py` (new) · `bff/routers/agent_presets.py` (widened) · `bff/routers/runs.py` (threading + echo).
- **Port(s) in progress:** `InferenceBackend` protocol landed as a health-inventory + selection layer ABOVE `route_by_role()`. Additive; default behavior byte-for-byte preserved.

## Completed this session

- **C then A executed in order.**
  - **C (plan reconciliation, prior commit `cb23905`):** amended Stage 2 plan (`docs/reconciliation-plan-stage-2.md`, canonical) to match the live `model_router.py` (dual vLLM roles per ADR-009 §3a, `RoleRoute`, supervisor coalescing, request-cap short-circuit). Rewrote Stage 2 section of `docs/reconciliation-plan-v1.md` as a summary + pointer.
  - **A (Stage 2.1 backend layer, this commit):** new `bff/services/inference_backends/` package (six adapters + registry + protocol + shared probes), new `GET /api/inference-backends` router, additive `backend_id: str | None = None` on `route_by_role`, widened `AgentPreset` types + reseeded with three local presets (ap-1 coder vLLM canonical, ap-2 planner vLLM, ap-3 Ollama fallback), `CreateRunRequest.backendId` threading, and `agentPresetId` echo on run responses.
- **Two KNOWN_ISSUES entries closed** and moved to `DEBUG_LOG.md` with fix details:
  - "Agent-preset `ModelId` is a static Literal, no local endpoints wired" (2026-08-05).
  - "`GET /api/runs/{id}` returns `agentPresetId: null` on succeeded runs" (2026-08-05).
- **36/36 targeted BFF tests pass** in the sandbox venv (`bff/tests/test_model_router.py` + `bff/tests/test_inference_backends.py`). The `backend_id=None` regression test locks the invariant that the default path is unchanged.

## Remaining before current Definition of Done

Amended Stage 2 DoD, remaining items:

1. **Stage 2.2 (frontend `HealthBadge` + `BackendSelector` + wiring):**
   - `HealthBadge` reusing existing `badge badge--success/warning/muted/error` CSS classes (verified in `src/features/mcp/McpServerCard.tsx`; do NOT introduce new Tailwind bg-* classes).
   - `BackendSelector` as a radio group (not `<select>`) with per-item badge + latency + error tooltip. Renders in the order of `BACKEND_REGISTRY.keys()`.
   - Wired into Agent Presets editor (existing pages: `src/features/agent-presets/AgentPresetsPage.tsx`, `AgentPresetCard.tsx`) and the run-creation form.
   - React Query hook `useInferenceBackends()` following the same pattern as `src/features/agent-presets/hooks.ts` (queryKey + fetch + auto-refresh cadence to be decided in 2.2).
   - `AgentPreset` schema on the frontend needs to grow `backendId?: BackendId | null` and `role?: RoleHint | null` (see `src/features/agent-presets/schemas.ts`).
2. **Stage 2.3 (docs-only):** `docs/colossus-inference-setup.md` with SM_120 flag matrix for llama.cpp / vLLM / SGLang. No new builds on Colossus.
3. **Stage 2.4 (VRAM-aware quant + concurrency):** `bff/services/hardware.py`, `bff/services/quant_selector.py`, `bff/services/concurrency.py`, `GET /api/inference-backends/concurrency-limit`, `ConcurrencyLimitDisplay` on the Settings page (`src/app/(dashboard)/settings/page.tsx`).
4. **Exit gate:** full manual checklist in `docs/reconciliation-plan-stage-2.md` § "Stage 2 exit gate", including an F.3 SWE-bench 5-task smoke re-run to confirm additive `backendId` did not regress role-based routing (must land inside the smoke-30 v2 regression band: 22–38% raw pass@1).

## Open questions / awaiting user answer

- **AgentPreset SQLite persistence** (Stage 1.5 leftover): still in-memory. Deferred to Stage 3. Not blocking Stage 2 exit. If a preset created via the UI must survive a BFF restart before Stage 3 lands, flag it and we roll it into Stage 2.
- **Playwright coverage timing for Stage 2.2:** amended plan has a `BackendSelector` visual check in the exit gate. Confirm whether to author the spec inside Stage 2.2 or as a separate F.16-style visual slice.

## Exact next action

Execute **Stage 2.2** per `docs/reconciliation-plan-stage-2.md` § 2.2, starting with:

1. On Colossus, verify the new backend package loads cleanly under the live BFF venv and the `GET /api/inference-backends` endpoint returns 200 (Ollama should probe healthy since it's currently holding the GPU per the 22:07 EDT `nvidia-smi` snapshot; every vLLM role should be `unhealthy` since `live_role: none`).
2. Sync the frontend `AgentPreset` schema in `src/features/agent-presets/schemas.ts` with the widened backend contract (`backendId`, `role`, free-form `model`).
3. Author `src/features/inference-backends/` (feature folder): `api.ts` + `hooks.ts` + `HealthBadge.tsx` + `BackendSelector.tsx` + `schemas.ts` mirroring the agent-presets feature layout.
4. Wire `BackendSelector` into `AgentPresetCard.tsx` (edit surface) and the run-creation form.
5. Playwright spec: assert `/agent-presets` renders the three seed presets (ap-1 default, ap-2 planner, ap-3 Ollama) with the correct backend badges.

Colossus is on `main` at the Stage 2.1 landing commit; working tree expected clean after next `git pull`. Do NOT touch `bff/services/model_router.py` beyond the additive `backend_id` param already landed. Do NOT delete or simplify the supervisor path, `_supervisor_ensure` locks, `_vllm_role_health`, or the Ollama fallback logic. Every code path listed under "Do NOT delete or simplify" in the amended plan § 2.0 is protected by tests and ADR-009 §3a.
