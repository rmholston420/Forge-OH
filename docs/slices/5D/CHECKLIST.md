# Slice 5D — Hardening Checklist

Work through every item in order. Do not mark done until verified.

## Agent Contract Files
- [x] `AGENTS.md` created at repo root with all non-negotiable rules
- [x] `DOMAIN_MODEL.md` created at repo root with canonical object table
- [x] `docs/DEFINITION_OF_DONE.md` created with full DoD checklist

## Per-Slice Route Contracts
- [x] `docs/slices/1A/README.md`
- [x] `docs/slices/1B/README.md`
- [x] `docs/slices/1C/README.md`
- [ ] `docs/slices/2A/README.md` (file diffs)
- [ ] `docs/slices/2B/README.md` (terminal)
- [ ] `docs/slices/2C/README.md` (artifacts)
- [ ] `docs/slices/3A/README.md` (workspaces)
- [ ] `docs/slices/3B/README.md` (MCP / plugins)
- [ ] `docs/slices/3C/README.md` (secrets)
- [ ] `docs/slices/4A/README.md` (browser)
- [ ] `docs/slices/4B/README.md` (observability)
- [ ] `docs/slices/4C/README.md` (trace explorer)
- [ ] `docs/slices/5A/README.md` (approvals)
- [ ] `docs/slices/5B/README.md` (fork/compare)
- [x] `docs/slices/5C/README.md`
- [x] `docs/slices/5D/README.md`
- [ ] `docs/slices/5E/README.md` (model router hardening)

## Feature Flag Registry
- [x] `src/lib/feature-flags/index.ts` with all slice flags
- [x] All flags default to `false` in non-CI environments
- [x] `NEXT_PUBLIC_FEATURE_BUILD_HARDENING_ENABLED` always `true`

## Seed Data
- [x] `src/tests/fixtures/seed.ts` with deterministic IDs
- [x] Seed IDs used in all fixture files for screenshot test stability

## MSW Handler Coverage
- [x] `GET /api/runs` handler
- [x] `POST /api/runs` handler
- [x] `GET /api/runs/:runId` handler
- [x] `GET /api/runs/:runId/events` handler
- [x] `GET /api/workspaces` handler
- [x] `GET /api/secrets` handler
- [x] `GET /api/plugins` handler
- [x] `GET /api/integrations/mcp` handler
- [x] `GET /api/agents/presets` handler
- [x] `POST /api/lms/context` handler
- [x] `GET /api/lms/context/:sessionId` handler
- [x] `POST /api/lms/package` handler
- [x] `GET /api/observability/summary` handler
- [x] `GET /api/runs/:runId/traces` handler

## Tests
- [x] `src/tests/unit/schemas.test.ts` — Zod schema validation
- [x] `src/tests/unit/feature-flags.test.ts` — flag resolution
- [x] `src/tests/unit/status-utils.test.ts` — run status color/label mapping
- [ ] Integration tests for run creation happy path
- [ ] E2E smoke: all primary routes load
