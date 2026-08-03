# Forge-OH Session Handoff

_Last updated: 2026-08-02 22:15 EDT_

## Current stage
**Build sequencing:** Stage 2 (rip out non-Forge scaffolding, stand up minimal Runs slice) — **COMPLETE**.

## Completed this session
- Removed auth / RBAC / LMS scaffolding: 69 files, `-3849 / +130` (`d0ebea5`)
- Aligned Python deps to openhands-agent-server 1.40.0 (`a4d6c8c`, `8cf9f4c`)
- Fixed root `/` redirect (→ `/runs`), deleted orphan auth e2e tests (`30947e7`)
- Routed the last stray client-side `fetch('/api/…')` calls through `bffFetch` (`e92703e`)
- Bulk-fixed BFF port defaults `8000 → 8081` across 25 files (`app/api/**/route.ts`, `features/**/api.ts`, streaming socket, `useRunStream`); removed `credentials: 'include'` (`32fa5d9`)
- Added `.env.local.example` with both `NEXT_PUBLIC_BFF_URL` and `BFF_URL`
- Added `scripts/debug-frontend.ts` Playwright diagnostic (`409a54d`, `1d4937e`)
- **Verified GREEN via Playwright:** `/runs` renders, `GET :8081/api/runs 200`, zero console/page/request errors

## Running services (Colossus)
- `openhands-agent-server` on `http://127.0.0.1:8090`
- BFF (`uvicorn bff.main:app_with_sio`) on `http://127.0.0.1:8081`
- Frontend (`pnpm dev`) on `http://localhost:3000`
- Ollama on `http://localhost:11434` — models: `qwen3.6:35b-a3b` (primary), `qwen3-coder:30b` (fast)

## Cosmetic warnings deferred (non-blocking)
- `experimental.typedRoutes` → move to `typedRoutes` in `next.config.ts`
- `middleware` file convention → rename to `proxy`
- pnpm ignored-builds warning (already approved locally with `pnpm approve-builds`)

## Next action — Stage 3
Vertical slice: **real run creation + event stream**.

1. Rewrite `bff/routers/runs.py` `POST /api/runs` to call OpenHands agent-server:
   - `POST http://127.0.0.1:8090/api/conversations` with body pattern:
     - `model: openai/qwen3.6:35b-a3b`
     - `base_url: http://localhost:11434/v1`
     - `api_key: ollama`
     - `native_tool_calling: false`
     - `usage_id: colossus-ollama`
   - Persist mapping `run_id <-> conversation_id` in SQLite.
2. Add BFF endpoint `POST /api/runs/{run_id}/message` → `POST /api/conversations/{cid}/events` on agent-server.
3. Add BFF endpoint `GET /api/runs/{run_id}/events` streaming from agent-server SSE `/api/conversations/{cid}/events/stream`.
4. Wire frontend `NewRunComposer` → `useRuns().createRun` → returned run id → navigate to `/runs/{id}` (already implemented).
5. Consolidate duplicate `openhands_client`: keep `bff/openhands_client.py`, delete `bff/services/openhands_client.py` shim.

## Open questions / ambiguities
_None outstanding._ Ready to start Stage 3 on next turn.
