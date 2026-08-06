# Forge-OH Session Handoff

## Current stage

**Stage 6.2 IN PROGRESS — code written + pushed, awaiting DoD verification on Colossus.**

Locked decisions (2026-08-06):
- SDK probe done: only three condensation classes exist in v1.40.0 (`Condensation`, `CondensationRequest`, `CondensationSummaryEvent`) — spec's `CondensationEvent` + `turns_summarized` + `artifact_manifest` do not exist.
- One visual icon (🗜️) shared across all three normalized types.
- Reuse existing EventCard + raw-expand pattern (no dedicated `<details>` variant).
- Generic dev-only injection endpoint at `POST /api/_debug/inject-event`, gated behind `FORGE_TIMELINE_DEBUG_INJECT=1`. Returns 404 when disabled.

## What was completed this session

**Stage 6.1 (DoD met, closed):** SearXNG SearchPort + SearxngAdapter vendored, `search_web` OpenHands tool, BFF bridge endpoint, EventCard 🔍 icon, backend + FE tests, E2E screenshot committed (commit `0c60df0`). See prior BUILD_LOG entries.

**Stage 6.2 (code complete, DoD pending):**
- `bff/services/event_normalize.py` — three new normalized types + summary helpers + dispatch branches.
- `bff/routers/debug.py` — generic dev-only injection endpoint.
- `bff/main.py` — router mounted.
- `bff/tests/test_event_normalize_condensation.py` (17 tests) + `bff/tests/test_debug_inject_endpoint.py` (8 tests).
- `src/components/domain/EventCard.tsx` — 🗜️ icons for all three condensation types.
- `src/tests/unit/EventCard-condensation.test.tsx` (4 tests).
- `src/tests/e2e/condensation-timeline-marker.spec.ts` — Playwright DoD spec.

## What remains before Stage 6.2 Definition of Done

User verification on Colossus:

```bash
cd ~/dev/forge-oh && git pull origin main
source .oh-venv/bin/activate

pytest bff/tests/test_event_normalize_condensation.py bff/tests/test_debug_inject_endpoint.py -q
pnpm test:unit src/tests/unit/EventCard-condensation.test.tsx

export FORGE_TIMELINE_DEBUG_INJECT=1
export FORGE_SEARXNG_BASE_URL=http://127.0.0.1:18888
./scripts/forge-restart.sh

PLAYWRIGHT_START_PROD=1 PLAYWRIGHT_GPU_STRIP_PUSH=1 \
  pnpm test:e2e src/tests/e2e/condensation-timeline-marker.spec.ts
```

Expected: 25 backend tests pass, 4 FE unit tests pass, E2E test injects a Condensation, 🗜️ card appears on run-detail, screenshot auto-committed and pushed.

If any test fails, report the output and the agent will fix immediately in the next turn (do NOT hand back a script).

## Open questions / ambiguities awaiting an answer

**Blocking:** None for Stage 6.2 code (all four ambiguities resolved 2026-08-06).

**Non-blocking follow-ups:**
- The memory E2E spec (`src/tests/e2e/memory-timeline-marker.spec.ts`) still has the latent REPO_ROOT + `import.meta` bugs fixed in the search spec at commit `2175c51`. Fix opportunistically if re-run.
- `forge-restart.sh` needs `FORGE_TIMELINE_DEBUG_INJECT=1` and `FORGE_SEARXNG_BASE_URL` to propagate to the BFF process. Confirmed to work by exporting before restart; if the script strips env, we'll need to source `.env.forge` or similar.

## Exact next action

**User:** run the verification block above on Colossus and report results. Then next stage is **6.3 — Idempotency ledger** (per `docs/reconciliation-plan-stage-6.md` §6.3).
