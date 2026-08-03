# Forge-OH Session Handoff

_Last updated: 2026-08-02 22:30 EDT_

## Current stage
**Build sequencing:** Stage 3 (first vertical slice — real conversation create → run detail → live events). Code committed. **Awaiting manual browser verification.**

## Completed this session
- Stage 2 verified GREEN via Playwright (previous handoff).
- Stage 3 code:
  - Added `bff/services/event_relay.py` — Socket.IO polling relay.
  - Rewrote `bff/routers/runs.py`: real agent-server calls for `GET /runs`, `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/events`.
  - Wired Socket.IO handlers + relay hookup in `bff/main.py`.
  - Deleted `bff/services/openhands_client.py` shim; deleted `src/lib/hooks/useRunStream.ts` duplicate + its two orphan tests.

## Running services (Colossus)
- `openhands-agent-server` on `http://127.0.0.1:8090`
- BFF (`uvicorn bff.main:app_with_sio`) on `http://127.0.0.1:8081`
- Frontend (`pnpm dev`) on `http://localhost:3000`
- Ollama on `http://localhost:11434` — model `qwen3.6:35b-a3b`

## Next action — verify Stage 3 end-to-end
1. On Colossus: `cd ~/dev/forge-oh && git pull`
2. Restart BFF terminal: `^C` then rerun uvicorn (needs to reload event_relay + Socket.IO handlers).
3. Frontend hot-reloads on its own; hard-reload the browser.
4. In browser at `http://localhost:3000/runs`:
   - Click **New Run** → enter a real task prompt (e.g. `"Create hello.py that prints Hello, Colossus"`) → submit.
   - Expect: redirect to `/runs/<uuid>`, status shows `running` (or `queued` transitioning to `running`).
   - Watch the event timeline populate with real Action/Observation events.
5. Run `npx tsx scripts/debug-frontend.ts` afterward and paste the summary (adjust the script to navigate to the created run URL if needed).

## Ambiguities flagged during design (resolved by user)
- Live event delivery: BFF polls `events/search` (agent-server has no SSE/WS), relays via Socket.IO. ✅
- run_id == conversation_id. ✅
- Stateless BFF. ✅
- Keep model_router. ✅
- Per-run workspace dirs. ✅ (`workspace/runs/<cid>/`)
- Tool set: `terminal`, `file_editor`, `task_tracker`, `browser_tool_set`. ✅

## Known open items (not blocking Stage 3 DoD)
- The `events/search` response schema is `{}` (undocumented). Code accepts three common shapes (bare list, `items:[]`, `data:[]`) — if agent-server returns a different envelope we'll see empty timelines and need to log the raw payload.
- Post-hoc reconnect: if BFF restarts mid-run, `GET /runs/{id}` restarts the relay from cursor `None` (may re-emit historical events). Deferred cleanup.

## Explicitly deferred (per plan)
- Files/diff (Stage 4), lifecycle controls (Stage 5), workspaces (Stage 6), plugin-mode.
