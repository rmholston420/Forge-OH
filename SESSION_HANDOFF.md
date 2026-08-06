# SESSION_HANDOFF — Forge-OH

**Last touched:** 2026-08-06 01:10 EDT

## Current build-sequencing position

- **Stage 4** (RepoGraph + LSP retrieval), `docs/reconciliation-plan-stage-4.md`.
- **§ 4.2 + § 4.3 CLOSED** — automated gate + Playwright PASS (BUILD_LOG 2026-08-06 00:47 EDT).
- **§ 4.4 CLOSED** — Serena LSPClient live on Colossus (BUILD_LOG 2026-08-06 01:10 EDT). `curl /api/mcp/serena/ping` returns 21 tools.
- **§ 4.5 (DozerDB consolidation) — NEXT.** Hard blocker for Stage 4 exit gate. Requires user sign-off on Option A vs Option B before implementation.

## What was completed this session

1. Pass 3 (§ 4.4) shipped in `8def365` + hotfix `4dea63d` + close-out (next commit):
   - `bff/services/mcp_bootstrap.py` — idempotent Serena registration on startup via the shared `openhands_client` (agent-server direct, not BFF-self-HTTP).
   - `bff/services/event_normalize.py` — 11 Serena LSP tools map to `type=lsp_<op>`.
   - `bff/settings.py` — `SERENA_ENABLED`, `SERENA_WORKSPACE_DEFAULT`, `SERENA_PIN_SHA=c7af2c09`.
   - `src/components/domain/EventCard.tsx` — LSP badge + 11 lsp_* icons.
   - `docs/adr/018-serena-lspclient-integration.md` — ADR with amendment banner.
   - `docs/reconciliation-plan-stage-4.md` — Stage 4 plan into repo.
   - `PORTING_LEDGER.md` — Serena entry (dependency-only, SPDX MIT, pinned SHA).
   - `AGENTS.md` — "Three-Tier Retrieval Cascade" section (LSP → RepoGraph → grep).
   - Tests: 10 async cases in `test_mcp_bootstrap.py`, 6 LSP cases in `test_event_normalize.py`, 4 cases in `EventCard-lsp.test.tsx`.

2. Verified end-to-end on Colossus (2026-08-06 01:09 EDT):
   - Automated gate: `pytest -q` **10/10**, `pnpm typecheck` clean, `pnpm test:unit` 4/4, `pnpm build` clean.
   - Live gate: Serena registered upstream with `stdio` / `uvx` / pinned SHA; ping returns `ok:true` with 21 tools including all six LSP ops the frontend UI knows about.

## What remains before Stage 4 is fully closed

§ 4.5 DozerDB consolidation. Two options:

- **Option A — Shared DozerDB.** RepoGraph (existing `forgeoh` DB) and Kosmos Tektos (future donor) live in one DozerDB instance, separate database names. Simpler ops on Colossus; potential Kosmos-donor overlap of procedure calls (`dozer.*`).
- **Option B — Dedicated Forge-OH DozerDB.** Keep the current `graphstack/dozerdb:5.26.27` container Forge-OH-only. Kosmos gets its own instance. More containers, but zero namespace overlap.

**Action for next session:** inspect Kosmos donor for `dozer.*` procedure calls (from `~/dev/rigpa-lms/` or wherever the donor lives), then present both options with a recommendation to the user. Do NOT start implementation until user signs off — the reconciliation plan flags this as requiring an ADR.

## Open questions / ambiguities awaiting user answer

**§ 4.5 sign-off:** Option A (shared DozerDB) vs Option B (dedicated). Recommendation to be attached after Kosmos-donor inspection.

## Exact next action

1. `cd /tmp/foh-work && rm -rf /tmp/foh-work` (or wherever the working checkout is), then re-clone if needed.
2. Inspect Kosmos donor for `dozer.*` procedures: `grep -rn "dozer\." ~/dev/rigpa-lms/ 2>/dev/null | head -30` (adjust path if donor lives elsewhere).
3. Read `docs/reconciliation-plan-stage-4.md § 4.5` for the DoD.
4. Draft an ADR-019 skeleton with Option A / Option B / recommendation; present to user for approval before writing any code.
5. On user sign-off, implement per approved option, log in BUILD_LOG + PORTING_LEDGER (if any donor code lifted), then re-run the full Stage 4 exit-gate sweep.
