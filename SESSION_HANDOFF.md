# Forge-OH Session Handoff

## Current stage

**Stage 5.6b — CLOSED (2026-08-06 04:09 EDT).** All Definition-of-Done gates green on Colossus.

Next slice: **Stage 5.6c** — memory-inspector page + `/api/memory/recent-writes` endpoint (see below).

## Stage 5.6b — Definition of Done (all met)

- [x] `consult_memory` in `GET /api/tools/` after `forge-restart.sh` (verified 2026-08-06 03:54 EDT).
- [x] `POST /api/memory/emit-consultation` returns 200 with wire event on Colossus (verified `emit=200`).
- [x] `pytest openhands_tools_ext/tests/memory/test_consult_memory_tool.py bff/tests/test_memory_emit_endpoint.py -q` — **21 passed** (2026-08-06 04:07 EDT).
- [x] Playwright spec `memory-timeline-marker.spec.ts` passed in 6.3 s (2026-08-06 04:08 EDT).
- [x] `screenshots/memory-timeline-marker.png` on `origin/main` at commit `fff2311` — 🧠 EventCard on run-detail.
- [x] PORTING_LEDGER + BUILD_LOG + DEBUG_LOG entries filed.

## Completed this session

- **Tool:** `openhands_tools_ext/memory/tools/consult_memory.py` — `ConsultMemoryAction`/`Observation`/`Executor`/`ToolDefinition` with `register_tool` at import time. Semantic tier only; other tiers raise `NotImplementedError` before any I/O. Sync executor (SDK v1.40.0 contract) drives async `MemoryPort.search_semantic` via `asyncio.run`.
- **Bridge endpoint:** `POST /api/memory/emit-consultation` on the BFF, gated by `FORGE_MEMORY_EMIT_ENABLED=1` or a composed `MemoryPort`. Returns 200 with the normalized wire event even if the Socket.IO emit swallows.
- **Auto-registration:** `scripts/forge-up.sh` launches agent-server with `--import-modules openhands_tools_ext.memory.tools.consult_memory`.
- **Unit tests:** `openhands_tools_ext/tests/memory/test_consult_memory_tool.py` (15 cases) + `bff/tests/test_memory_emit_endpoint.py` (6 cases).
- **Live DoD spec:** `src/tests/e2e/memory-timeline-marker.spec.ts` — resolves a real conversation id (reuses existing if any, falls back to Ollama preset `ap-3` via BFF create-run), navigates to `/runs/{id}` so `useRunStream` joins the socket room, POSTs the emit endpoint, asserts the EventCard button scoped by its accessible name, auto-pushes screenshot on `PLAYWRIGHT_GPU_STRIP_PUSH=1`.
- **Screenshot:** `screenshots/memory-timeline-marker.png` on `origin/main`.
- **Logs:** PORTING_LEDGER hand-authored entry; BUILD_LOG entry (2026-08-06 03:43 EDT); five DEBUG_LOG entries covering all fixup findings.

## Stage 5.6b commit trail on `origin/main`

1. `65d41e0` — initial code (tool + endpoint + agent-server import + tests + spec)
2. `981ba99` — resolve_tool signature tolerance + Playwright `PLAYWRIGHT_START_PROD` pattern
3. `95ab726` — registry-dict probe + vLLM-independent DoD (agent-server reuse path)
4. `74cf797` — resolver-closure value check + Ollama preset (`ap-3`) fallback
5. `4b9a60f` — scope 🧠 assertion to EventCard button (fix strict-mode 3-element match)
6. `fff2311` — Playwright auto-pushed the screenshot

## Follow-up items (out of Stage 5.6b scope)

- **BFF `blocked`-routing path returns `data.id=""`.** When routing fails (e.g. vLLM coder down), `POST /api/runs` returns HTTP 200 with an empty `data.id` and `status="blocked"`. The frontend cannot navigate to a run without an id, so the "blocked" UI state is unreachable. Recommend either persisting a synthesized id + shell run row or returning 503 on routing failures. Full symptom + reproduction in `DEBUG_LOG.md` (2026-08-06 04:00 EDT). Warrants its own ADR + KNOWN_ISSUES entry when picked up.

## Next slice — Stage 5.6c (Memory-inspector page)

Source: `Forge-OH-reconciliation-plan-v1-stage-5.md` §5.6.3.

**Scope:**

1. **Backend** — `GET /api/memory/recent-writes?limit=50` in `bff/routers/memory.py`. Query DozerDB `MATCH (m:MemoryEvent) RETURN m ORDER BY m.created_at DESC LIMIT $limit` and return `{data: [{id, content, provenance, confidence, createdAt}, ...]}`. Reuse the driver already composed by Stage 4/5.
2. **Frontend** — `src/features/memory-inspector/MemoryInspectorPage.tsx` (TanStack Query hook + table with content / provenance / confidence / time), route at `src/app/(dashboard)/memory-inspector/page.tsx`, sidebar entry matching existing nav-item pattern. Follow the masked-but-inspectable convention from `src/features/secrets/SecretRow.tsx`.
3. **Tests** — pytest for the BFF endpoint (empty, populated, limit clamp), Playwright spec that seeds a memory event via existing `scripts/seed_memory_event.py` (or the ADR-016-compliant equivalent), navigates to `/memory-inspector`, asserts the row is visible with provenance + confidence.

**Definition of Done for 5.6c:**

- [ ] `GET /api/memory/recent-writes` returns 200 with paged records on Colossus.
- [ ] `/memory-inspector` route renders the recent-writes table.
- [ ] Sidebar entry navigates to it.
- [ ] Playwright spec passes; screenshot `screenshots/memory-inspector-writes.png` on `origin/main`.
- [ ] BUILD_LOG + PORTING_LEDGER (if any donor is used) entries filed.

**Stop condition:** DoD-6 checkboxes above green; do not continue to Stage 5.6d (full end-to-end verify via a real task) in the same slice.

**Open decisions / clarifications for user before starting 5.6c:**

- Placement: the spec allows either "tab inside Skills/Microagents (Stage 6.6, not yet built)" or "own minimal standalone route." Standalone route is the currently indicated default. Confirm before touching sidebar nav.
- Sort order: `created_at DESC` per the spec; confirm no per-run filtering is needed for this first slice.
- Empty-state UI: should it render nothing, a "no memory writes yet" placeholder, or a link to the emit-consultation debug flow?

## Exact next action

Ask the user for confirmation on the three open decisions above, then start Stage 5.6c with the BFF endpoint (backend first; frontend can be built against a real endpoint response).

## Restart / verify recipe (unchanged)

```bash
cd ~/dev/forge-oh && git pull
bash scripts/forge-restart.sh
bash scripts/forge-status.sh
curl -s http://127.0.0.1:8090/api/tools/ | grep -o consult_memory
curl -s -o /dev/null -w "emit=%{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -d '{"runId":"probe","tier":"semantic","query":"probe","resultCount":0}' \
  http://127.0.0.1:8081/api/memory/emit-consultation
.oh-venv/bin/pytest \
  openhands_tools_ext/tests/memory/test_consult_memory_tool.py \
  bff/tests/test_memory_emit_endpoint.py -q
cd src
PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
PLAYWRIGHT_GPU_STRIP_PUSH=1 \
  npx playwright test tests/e2e/memory-timeline-marker.spec.ts --reporter=list
```
