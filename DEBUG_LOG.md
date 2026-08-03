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

## 2026-08-02 23:12 EDT — POST /api/runs 422: missing 'title'
- Symptom: curl -s -X POST /api/runs with taskPrompt+agentPresetId+workspaceId returned "422 Unprocessable Entity ... loc=[body,title] Field required"
- Stage: 4 (Stage 4 e2e prep)
- Root cause: CreateRunRequest in bff/routers/runs.py declares title: str (required). Frontend auto-generates title from prompt; direct curl smoke-tests must include it.
- Fix: include "title":"<label>" in the JSON body.
- Files changed: none (docs-only lesson).

## 2026-08-02 23:17 EDT — /runs/{id}/files/{path} 404 on unencoded absolute paths
- Symptom: `curl /api/runs/<cid>/files/workspace/hello.txt` returned 404 while the file appeared in the listing.
- Stage: 4
- Root cause: reconstructed paths are absolute (e.g. `/workspace/hello.txt`) because the agent reports them that way. FastAPI's `{file_path:path}` captured `workspace/hello.txt` (no leading slash) since the router prefix `/files/` consumes the slash. Lookup mismatched.
- Fix: after first miss, retry lookup with a `/` prefix. Preserves the correct-encoded frontend path (`%2Fworkspace%2Ffoo` decodes to `/workspace/foo` and matches on first try).
- Files changed: bff/routers/runs.py

## 2026-08-02 23:24 EDT — New Run modal drops the prompt intermittently
- Symptom: Playwright e2e submits with PROMPT set; agent replies "I don't see a specific task in your message. The task description section appears to be empty." Reproduced twice on qwen3.6:35b-a3b (runs 55c04..., b7b1b140).
- Stage: 3 leftover (Stage 4 discovery)
- Root cause: NOT confirmed. Two candidates:
  a) Frontend's New Run modal doesn't wire the textarea 'value' → POST body 'taskPrompt' correctly.
  b) scripts/e2e-run.ts fills a textarea that's not the actual prompt input (the modal may have multiple textareas — title/description fields).
- Direct POST to /api/runs with taskPrompt in the body works correctly (run b983c992 executed the file_editor tool 2x).
- Workaround: use direct BFF POST for tool-invoking runs; browser-level submit still opens/creates a run (title-only).
- Fix deferred: not in Stage 4 scope. Log for follow-up in Stage 5 e2e polish (or as a Stage 3.5 hotfix if it blocks Stage 5).
- Files changed: none.

## 2026-08-02 23:24 EDT — file_editor 'create' can partially succeed with malformed path
- Symptom: One agent invocation of file_editor with command=create produced an ObservationEvent with is_error=True and no path; the model then retried and succeeded.
- Stage: 4
- Root cause: qwen3.6:35b-a3b occasionally emits raw XML tags inside the JSON tool-call arguments (observed: 'path=/workspace/stage4-final.txt</path>\n<parameter=file_text>Stage 4 DoD proof').
- Reconstruction behavior: file_diff_reconstruction.py already drops is_error=True observations, so the failed attempt is invisible in /files output. Behavior is correct.
- Files changed: none. Filter was proactive.
