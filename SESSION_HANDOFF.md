# Forge-OH Session Handoff

## Current stage

**Stage 6.1 — Ported SearXNG web-research tool. Backend + frontend wiring COMPLETE, awaiting local verification on Colossus.**

Locked decisions (from 2026-08-06 04:44 EDT session): image `searxng/searxng:2026.8.4-c63835bd2@sha256:dc5c10fda6818dfef7abfdf9f451b898242c3321514a9524af215cbedc79c89b`, `ops/compose/searxng.yml` on `127.0.0.1:18888`, verbatim Kosmos `settings.yml` minus mechanical rewrites, env var `FORGE_SEARXNG_BASE_URL`, cheap sync emit gate (B1a).

## What was completed this session

1. **Kosmos donor files vendored verbatim** into `openhands_tools_ext/search/` with SHA-256 equality proof in `PORTING_LEDGER.md`. Mechanical rewrites only (import paths, env-var name, User-Agent, default port).
2. **`search_web` OpenHands tool** written and registered at import time — auto-loaded by `scripts/forge-up.sh` via `--import-modules openhands_tools_ext.search.tools.search_web`.
3. **BFF bridge endpoint** `POST /api/search/emit` (`bff/routers/search.py`) + producer service (`bff/services/search_events.py`). Feature-gated by `FORGE_SEARCH_EMIT_ENABLED=1` OR `FORGE_SEARXNG_BASE_URL` — cheap sync check, no network I/O in the hot path.
4. **Frontend wiring:** `event_normalize.py` maps `WebSearchEvent → web_search`; `EventCard`'s 🔍 icon slot was already provisioned in Stage 5.
5. **Docker Compose:** `ops/compose/searxng.yml` + `searxng.settings.yml` + `README.md`. Loopback-bound `127.0.0.1:18888`, image pinned by digest.
6. **Test coverage:**
   - `openhands_tools_ext/tests/search/test_searxng_contract.py` (donor's 6 tests, adjusted for Forge-OH paths)
   - `openhands_tools_ext/tests/search/test_search_web_tool.py` (happy path, empty results, emit-on-failure, registration)
   - `bff/tests/test_search_emit_endpoint.py` (503 gate, both gate variants, 422 validation, Socket.IO resilience)
   - `src/tests/unit/EventCard-web-search.test.tsx` (icon + summary)
   - `src/tests/e2e/search-timeline-marker.spec.ts` (live emit + screenshot, mirrors 5.6b spec)
7. **Ledger + logs updated:** `PORTING_LEDGER.md`, `BUILD_LOG.md`, this `SESSION_HANDOFF.md`.

## What remains before Stage 6.1 Definition of Done

Purely local verification steps on Colossus (agent side did all the code changes it can):

```bash
# 1. Pull the branch
cd ~/dev/forge-oh
git pull origin main

# 2. Bring up SearXNG
docker compose -f ops/compose/searxng.yml up -d
curl -s "http://127.0.0.1:18888/search?q=probe&format=json" | jq '.query'   # expect: "probe"

# 3. Restart the stack so agent-server picks up the new --import-modules and BFF picks up the new router
source .oh-venv/bin/activate
export FORGE_SEARXNG_BASE_URL=http://127.0.0.1:18888
./scripts/forge-restart.sh

# 4. Backend test suites
pytest openhands_tools_ext/tests/search/ -q
pytest bff/tests/test_search_emit_endpoint.py -q
pytest bff/tests/ -q            # full BFF regression (expect 2 known-ignorable fails from KNOWN_ISSUES.md)
pytest openhands_tools_ext/tests/ -q

# 5. Frontend unit + typecheck + build
pnpm typecheck
pnpm test:unit src/tests/unit/EventCard-web-search.test.tsx
pnpm build

# 6. E2E DoD screenshot (needs BFF+agent+prod frontend up)
PLAYWRIGHT_START_PROD=1 PLAYWRIGHT_GPU_STRIP_PUSH=1 \
  pnpm test:e2e src/tests/e2e/search-timeline-marker.spec.ts
```

## Open questions / ambiguities awaiting an answer

None — all four Stage 6.1 blocking decisions are locked (see BUILD_LOG entry). The E2E spec is hand-authored (not sed-transformed) — if it needs adjustments (e.g., different heading selector, room name), fix in a follow-up.

## Exact next action

**User:** run the six-step verification block above on Colossus. Report any failing test / non-200 endpoint / missing screenshot.

**Then Stage 6.2:** Condensation visibility (per `docs/reconciliation-plan-stage-6.md` §6.2).
