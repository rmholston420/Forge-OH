# DEBUG LOG (append-only)

## 2026-08-02 22:32 EDT — ReactQuery ["runs","presets"] undefined + ZodError agentPresetId
- **Symptom:** Console: `Query data cannot be undefined ... key: ["runs","presets"]`, then `ZodError agentPresetId "expected string >=1 characters"` on run submit.
- **Affected stage/plugin/port:** Stage 3, BFF `bff/routers/agent_presets.py` HTTP contract vs frontend `src/features/runs/api.ts` envelope expectation.
- **Root cause:** BFF returned bare list; frontend `unwrap(result).data` expected `{data:[...]}` envelope. The Zod error is downstream: composer auto-selects `presets[0].id`, but presets never load → `agentPresetId` stays "" → schema min(1) fires.
- **Fix applied:** Wrap `list_presets()` in `{'data': [...]}` — matches every other BFF list endpoint contract.
- **Files changed:** `bff/routers/agent_presets.py`

## 2026-08-02 22:44 EDT — Real run finished, but events not reaching browser + list_runs 422
- **Symptom:** BFF log shows `list_runs: agent-server unreachable: 422 Unprocessable Entity for /api/conversations`. Also: run created + finished (execution_status=finished, 12k tokens) but event timeline in browser stayed empty; WebSocket connected then closed with no events forwarded.
- **Affected stage/plugin/port:** Stage 3, `bff/routers/runs.py` list endpoint + `bff/services/event_relay.py` Socket.IO emit + `bff/main.py` connect handler.
- **Root causes:**
  1. agent-server 1.40.0's `GET /api/conversations` is batch-get by ids, requires `ids` query param. Real list endpoint is `/api/conversations/search`.
  2. Backend emitted Socket.IO events `oh-event`/`oh-status`; frontend `useRunStream` listens for `event`/`status`. Wire protocol mismatch => zero events surfaced.
  3. Frontend sends `?runId=<uuid>` on WebSocket connect; backend read `?conversationId=<uuid>`. Room never joined.
- **Fix applied:** switch list to `/api/conversations/search`; rename Socket.IO emit event names to `event`/`status`; accept both `runId` and `conversationId` in Socket.IO connect + subscribe handlers.
- **Files changed:** `bff/routers/runs.py`, `bff/main.py`, `bff/services/event_relay.py`.

## 2026-08-02 22:57 EDT — Playwright polling never saw terminal status
- **Symptom:** e2e script waited full 180s timeout even though run finished in ~1s. BFF logs showed run reached `finished` state.
- **Affected:** scripts/e2e-run.ts
- **Root cause:** BFF single-item GET `/api/runs/{id}` returns `{data: {...}}` envelope, but polling loop read `d.executionStatus` directly on the outer object instead of `d.data.executionStatus`.
- **Fix applied:** unwrap `body?.data ?? body` before reading status. Also reduced poll interval 1500→1000ms and added `/events` fetch to the report.
- **Files changed:** scripts/e2e-run.ts
