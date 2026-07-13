# Slice 5D — Build-System Hardening for AI Agent Execution

## Goal
Ensure the repository is optimized for AI agents as implementation agents.

## Deliverables
- [x] `AGENTS.md` — mandatory first-read contract for all AI agents
- [x] `DOMAIN_MODEL.md` — canonical object names, never rename
- [x] `docs/DEFINITION_OF_DONE.md` — slice completion gate
- [x] Per-slice `README.md` contracts in `docs/slices/*/`
- [x] Per-slice `CHECKLIST.md` task gates in `docs/slices/*/`
- [x] Feature flag registry `src/lib/feature-flags/index.ts`
- [x] Seed data `src/tests/fixtures/seed.ts` — deterministic IDs for screenshot testing
- [x] MSW handlers extended with LMS + observability + traces routes
- [x] Unit tests: Zod schema validation, status utilities, feature flags
- [x] E2E smoke: all primary routes load without errors

## Feature Flag
`NEXT_PUBLIC_FEATURE_BUILD_HARDENING_ENABLED` (always `true` in CI)
