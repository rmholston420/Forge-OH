# Session Handoff

**Last updated:** 2026-08-05 22:38 EDT

## Current stage / plugin / port in progress

- **Stage:** Stage 2.2 — frontend `BackendSelector` + `HealthBadge` + preset-card badge fix (amended plan `docs/reconciliation-plan-stage-2.md § 2.2`).
- **Layer:** frontend only (Next.js UI + React Query). Stage 2.1 BFF layer is unchanged.
- **Adjacent:** Stage 2 completes when this ships and passes the visual-verification paste block on Colossus. No new ports; no ADR.

## Completed this session

1. Diagnosed Stage 2.1 Colossus verification: Ollama had auto-stopped between checks (unrelated to our code). User restarted with `sudo systemctl start ollama`. Endpoint returned correct per-entry health after that.
2. Confirmed Option B for Stage 2.2 (`:8080` collision between llama.cpp default and openhands-workspace HTML is documented-deferred — degraded state is the honest signal).
3. Fresh clone at commit `98763c6` (Stage 2.1 tip on main).
4. Frontend schema layer widened:
   - `src/lib/schemas/run.ts` — `BackendIdSchema` + `backendId` on `CreateRunRequestSchema`.
   - `src/features/agent-presets/schemas.ts` — `ModelIdSchema` → `z.string()`, added `BackendIdSchema` / `RoleHintSchema` / `backendId` / `role`.
   - `src/features/runs/schemas.ts` — optional `backendId` + `role` on loose preset.
   - `src/lib/api/endpoints.ts` — `INFERENCE_BACKENDS.list()`.
   - `src/lib/query/query-keys.ts` — `inferenceBackendKeys` + registration in `QUERY_KEYS` aggregate.
5. New feature folder `src/features/inference-backends/` with `schemas.ts`, `api.ts`, `hooks.ts` (10s refetch), `HealthBadge.tsx` (state→variant map), `BackendSelector.tsx` + `.module.css` (radio group, role-incompatible options disabled), `index.ts`.
6. Fixed `src/features/agent-presets/AgentPresetCard.tsx` — replaced hardcoded cloud MODEL_BADGES with dynamic model + backend + role chips (`data-testid="backend-chip-<id>"`).
7. Wired `BackendSelector` into `src/components/domain/NewRunComposer.tsx` via `Controller`; role passed from the selected preset so incompatible backends render disabled.
8. Added `src/tests/unit/HealthBadge.test.tsx` (6 cases) and `src/tests/e2e/backend-selector.spec.ts` (two live-BFF tests).
9. Static sanity in-sandbox: all `@/` imports resolve to real exports; all CSS tokens exist in `src/styles/tokens.css`.
10. BUILD_LOG entry appended (this session's full changeset).

## What remains before DoD

- **User runs the Colossus verification paste block** (produced next by the assistant): `pnpm typecheck`, `pnpm test:unit -- HealthBadge`, then `pnpm test:e2e -- backend-selector.spec.ts` against the prod frontend on `:3100`.
- If any of those fail, iterate before declaring Stage 2 DoD met.
- Preset edit drawer is explicitly **out of scope** (deferred to Stage 3 UX slice — no consumer exists in the current UI beyond the Zustand action).
- `:8080` llama.cpp collision remains documented-deferred.

## Open questions / ambiguity awaiting the user

None. Everything in scope is on `main` after the push.

## Exact next action

Run the Colossus verification paste block delivered in the assistant's message. On green, Stage 2 is DONE.
