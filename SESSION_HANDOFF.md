# Forge-OH Session Handoff

## Current stage

**Stage 5 exit gate — IN PROGRESS (2026-08-06 04:14 EDT).**

Stage 5.6 is fully shipped:
- **5.6a** (memory-inspector page + `GET /api/memory/recent-writes`) shipped 2026-08-06 03:15 EDT, commit `7ea3201`, ADR-024.
- **5.6b** (consult_memory tool + timeline marker) shipped 2026-08-06 04:08 EDT, commit trail `65d41e0 → fff2311 → 429a07d`.

Before opening Stage 6.1, the reconciliation-plan §"Stage 5 exit gate" must pass.

## Exit-gate — run this on Colossus and paste output

```bash
cd ~/dev/forge-oh && git pull

# 1. Backend unit tests (37 files under bff/tests/).
.oh-venv/bin/pytest bff/tests/ -q

# 2. Ported memory layer + tool tests (20 files under openhands_tools_ext/tests/).
.oh-venv/bin/pytest openhands_tools_ext/tests/ -q

# 3. TypeScript type check.
pnpm typecheck

# 4. Frontend unit tests (vitest).
pnpm test:unit

# 5. Production build (must exit 0).
pnpm build
```

**Known pre-existing failures** (documented in `KNOWN_ISSUES.md` — do NOT block the gate on these):

- `bff/tests/test_repograph_router.py::TestHealthNoPassword::test_returns_error_when_password_missing` — DozerDB dev container accepts empty password; test expects hardened Neo4j behaviour.
- `src/tests/unit/gitDiff.test.tsx :: FilesTab — Real git diff toggle > renders the toggle when run has a local workspace path` — pre-Stage-4 waitFor timeout.
- `src/tests/unit/AgentPresetCard.test.tsx :: AgentPresetCard > renders name and model badge` — pre-Stage-4 query failure.

Anything else that fails should be pasted so I can triage it.

## Manual checklist (already-shipped items — one-time visual confirmation)

Most items below are already covered by prior Playwright screenshots on `origin/main`; just confirm they still hold on your current Colossus state.

- [ ] `from openhands_tools_ext.memory.ports import memory, vector, embeddings` all import cleanly (one-line python check).
- [ ] Qdrant + Ollama embeddings adapters live: `curl :11434/api/tags` returns embeddings model; Qdrant collection reachable (Stage 5.2 verify path).
- [ ] DozerDB `search_semantic()` returns a real result (Stage 5.3 verify path).
- [ ] Provenance-less write rejected at port layer (Stage 5.4 verify path).
- [ ] ACE curation dedupe fires on a second identical observation (Stage 5.5 verify path).
- [ ] `MemoryConsultation` events render on run-detail — **already screenshotted:** `screenshots/memory-timeline-marker.png` (Stage 5.6b DoD).
- [ ] `/memory-inspector` reachable via sidebar with real writes — **already screenshotted:** `screenshots/memory-inspector-page.png` and `screenshots/memory-inspector-sidebar.png` (Stage 5.6a DoD).
- [ ] Every ported file has a `PORTING_LEDGER.md` entry with Kosmos commit hash.

## If everything passes

I write the "Stage 5 COMPLETE" BUILD_LOG entry and open Stage 6.1 (SearXNG port). Per the reconciliation plan:

> **Stage 6.1 exact next action:** port Kosmos's `ports/search.py` and `adapters/search/searxng/adapter.py` verbatim, deploy local SearXNG via docker-compose, wrap as an `openhands_tools_ext` tool.

Before touching Stage 6.1 code, I will restate the scope, ask about the docker-compose placement + SearXNG image pin, and confirm which Kosmos commit hash to source from.

## If something unexpected fails

Paste the failure block and I'll triage. If it's already logged in `KNOWN_ISSUES.md` we ignore it for the gate; otherwise it becomes a debug task before Stage 5 closes.

## Open follow-up (out of Stage 5 scope, still tracked)

- **BFF `blocked`-routing path returns `data.id=""`** — surfaced during Stage 5.6b DoD. When routing fails (e.g. vLLM coder down), `POST /api/runs` returns HTTP 200 with an empty `data.id`. Frontend cannot render a blocked run. Recommend synthesized id or 503. Details in `DEBUG_LOG.md` (2026-08-06 04:00 EDT). Needs its own ADR + KNOWN_ISSUES entry when picked up.

## Recent commit trail on `origin/main`

- `429a07d` — Stage 5.6b close-out (SESSION_HANDOFF + BUILD_LOG)
- `fff2311` — Playwright screenshot auto-push (5.6b DoD)
- `4b9a60f` — Stage 5.6b fixup #4 (🧠 EventCard scope)
- `74cf797` — Stage 5.6b fixup #3 (registry closure + ap-3 fallback)
- `95ab726` — Stage 5.6b fixup #2 (registry-dict probe + vLLM-independent DoD)
- `981ba99` — Stage 5.6b fixup #1 (resolve_tool signature + PLAYWRIGHT_START_PROD)
- `65d41e0` — Stage 5.6b initial code
- `7ea3201` — Stage 5.6a (memory-inspector + recent-writes)
