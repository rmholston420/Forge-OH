# Forge-OH Session Handoff

## Current stage

**Stage 6.1 — Ported SearXNG web-research tool (Kosmos `SearchPort`).**
Opened 2026-08-06 04:20 EDT after Stage 5 exit gate passed. **Blocked on four open decisions** — see below.

## Stage 5 status: COMPLETE

All exit-gate commands passed on Colossus (2026-08-06 04:15–04:19 EDT):

- `pytest bff/tests/` → 484 passed, 2 failed (both known-ignorable in `KNOWN_ISSUES.md`).
- `pytest openhands_tools_ext/tests/` → 324/324 passed.
- `pnpm typecheck` → exit 0.
- `pnpm test:unit` → 855 passed, 2 failed (both known-ignorable).
- `pnpm build` → compiled successfully; `/memory-inspector` route present.

DoD screenshots for 5.6a and 5.6b already on `origin/main`. Kosmos SHA for all Stage 5 ports: `c455165bca0d645f0d43572d0c286dca7033d31d`.

## Stage 6.1 scope (restated from reconciliation-plan-v1.md §6.1)

1. Port Kosmos `SearchPort` + SearXNG adapter verbatim from `github.com/rmholston420/kosmos` @ SHA `c455165bca0d645f0d43572d0c286dca7033d31d`. Four files, ~13 KB total.
2. Deploy local SearXNG via Docker Compose.
3. Wrap as `openhands_tools_ext` tool that thin-calls `SearchPort.search()`.
4. Frontend: distinct event type in run-detail timeline with query + source list + `provenance`.
5. Verify: agent calls the tool, SearXNG returns real results, provenance visible in the UI.

Zetesis research-loop modules (§6.1 optional follow-up) — **deferred**, not in Stage 6.1.

## Blocked — please answer these four questions before I write any code

1. **SearXNG container image pin.**
   - (a) Kosmos's exact image (whatever it uses in `ops/compose/searxng*.yml` if that exists) — I'll fetch and match.
   - (b) `docker.io/searxng/searxng:latest` — rolling, easy but violates the "no rolling tags" convention.
   - (c) Pin to a specific `searxng/searxng` tag by digest — I'll pick the most recent stable tag and record the digest in `PORTING_LEDGER.md`.

2. **Compose placement.**
   - (a) New file `ops/compose/searxng.yml` — matches the split-compose pattern established with `ops/compose/memory.yml`. **Recommended.**
   - (b) Add SearXNG service to the existing top-level `docker-compose.yml`.

3. **Host port binding.**
   - (a) Kosmos default `8888` — simplest if free on Colossus.
   - (b) Forge-OH-owned `18888` — avoids collision risk with other local search UIs.
   - (c) Something else — specify.

4. **SearXNG config (`settings.yml`).**
   - (a) Copy Kosmos's `settings.yml` verbatim if present at the pinned SHA.
   - (b) Start with a minimal Forge-OH-specific config (google + duckduckgo enabled, everything else disabled).

**Default if you say "just make the optimal call":** 1c (specific tag + digest), 2a (new `ops/compose/searxng.yml`), 3b (`18888` binding), 4a (verbatim Kosmos config if it exists at the pinned SHA; otherwise 4b).

## Once decisions are locked

1. `git fetch` the four donor files at pinned SHA, land them in `openhands_tools_ext/search/`.
2. Write `PORTING_LEDGER.md` entry with SHA-256 equality proof for each file.
3. Write `ops/compose/searxng.yml`, spin up on Colossus, `curl http://127.0.0.1:<port>/search?q=probe&format=json` returns 200.
4. Add `openhands_tools_ext.search.tools.search_web` tool, `register_tool()` at agent-server import time (same auto-import pattern as `consult_memory`).
5. Add `bff/routers/search.py` with `POST /api/search/emit` (mirrors `POST /api/memory/emit-consultation`).
6. Extend `bff.services.event_normalize.normalize_event` to map new `search_web` event kind → normalized `web_search` type.
7. Extend `EventCard` with a `web_search` variant (query, ranked result list with links, `provenance`).
8. Playwright spec `search-timeline-marker.spec.ts` (mirrors `memory-timeline-marker.spec.ts`).
9. Unit tests: `openhands_tools_ext/tests/search/test_search_tool.py`, `bff/tests/test_search_emit_endpoint.py`, contract test carried over from donor.
10. Screenshot + BUILD_LOG + SESSION_HANDOFF closeout.

## Out-of-scope follow-ups still tracked

- **BFF `blocked`-routing path returns `data.id=""`** — surfaced Stage 5.6b DoD. Frontend cannot render a blocked run. Recommend synthesized id or 503. Details in `DEBUG_LOG.md` (2026-08-06 04:00 EDT). Needs ADR + `KNOWN_ISSUES` entry when picked up.
- **`test_direct_sync_call_would_block_confirms_the_hazard`** — broken test premise, out of Stage 5 scope. See `KNOWN_ISSUES.md` 2026-08-06 04:17 EDT.

## Recent commit trail on `origin/main`

- `1d34d29` — openhands_tools_ext gpu `__init__.py` fix + hazard-test known-issue log.
- `de7b2d2` — Stage 5 exit gate initiated (BUILD_LOG + SESSION_HANDOFF).
- `429a07d` — Stage 5.6b close-out.
- `fff2311` — 5.6b Playwright screenshot auto-push.
- `4b9a60f`, `74cf797`, `95ab726`, `981ba99` — 5.6b fixups.
- `65d41e0` — Stage 5.6b initial code.
- `7ea3201` — Stage 5.6a.
