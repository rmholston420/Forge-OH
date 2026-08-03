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

## 2026-08-02 23:26 EDT — RESOLVED: New Run modal drops the prompt
- Root cause: NewRunComposer.tsx used field name "contextPrompt" while CreateRunRequestSchema declares "taskPrompt"; Zod stripped the mismatched field before POST.
- Fix: aligned the component's field name with the schema (src/components/domain/NewRunComposer.tsx).
- Verified via: fresh Playwright e2e (pending).

## 2026-08-02 23:29 EDT — /workspace is shared across runs (Stage 6 scope)
- Symptom: fresh Playwright run with a fixed filename gets ObservationEvent is_error=True "File already exists". Reconstruction correctly returns 0 mutations because the create failed and no successful mutation followed.
- Stage: leftover from Stage 3 (workspace_dir_placeholder); real fix is Stage 6 (workspaces).
- Workaround in e2e: scripts/e2e-run.ts now expands `{{TS}}` in PROMPT to a unique timestamp so successive e2e runs don't collide.
- Files changed: scripts/e2e-run.ts (PROMPT template variable).

## 2026-08-03 00:07 EDT \u2014 Client feature flags always false in browser bundles
- Symptom: With NEXT_PUBLIC_FEATURE_APPROVAL_GATE=true in .env.local and Next confirming the file at startup ("Environments: .env.local"), the NewRunComposer.tsx did not render the {approvalGateOn && ...} block. Playwright dump of the modal DOM showed no requireApproval checkbox and no hidden input for it. Purging .next/ and restarting did not fix it.
- Affected stage/plugin/port: Stage 1E (Approval Gate), src/lib/feature-flags/index.ts, all consumers of useFeatureFlag/isFeatureEnabled inside Client Components.
- Root cause: readEnvFlag() used a computed lookup: process.env[`NEXT_PUBLIC_FEATURE_${flag}`]. Next.js only inlines *literal* process.env.NEXT_PUBLIC_* reads into client bundles. Any computed key access returns undefined in the browser. Server components worked; client components silently disabled every flag.
- Fix: Replace the computed lookup with a static Record<FeatureFlag, string|undefined> in src/lib/feature-flags/index.ts, one literal process.env.NEXT_PUBLIC_FEATURE_<NAME> per flag, so Next inlines them all at compile time. readEnvFlag() now just returns STATIC_FLAG_VALUES[flag].
- Files changed: src/lib/feature-flags/index.ts.

## 2026-08-03 00:09 EDT \u2014 Reject doesn't reach a terminal state on its own
- Symptom: Stage 1E e2e leg 2 verified respond_to_confirmation {accept:false} returned 200 but the run then sat in agent-server 'idle' \u2192 BFF 'queued' indefinitely.
- Affected stage/plugin/port: Stage 1E (Approval Gate), bff/routers/runs.py reject_run().
- Root cause: agent-server's response to a rejected confirmation is to abort the tool call and return the conversation loop to idle. There is no terminal-on-reject transition. From the user's POV the run is still open.
- Fix: reject_run() now POSTs to /interrupt after respond_to_confirmation. /interrupt yields 400 when the conversation is already idle/finished; that branch is tolerated. Successful interrupt drives execution_status to 'paused' (agent-server's version of a hard-cancel state). BFF status map already routes paused\u2192paused, so the UI shows a paused run that can be resumed or fully stopped. This matches how OpenHands models cancellation.
- Files changed: bff/routers/runs.py.

## 2026-08-03 05:19 EDT — Multiple pages rendering as unstyled browser defaults

**Symptom:** Playwright screenshots on branch `agent/screenshots-20260803-050430` showed /settings, /workspaces action buttons, Run Overview message bodies, and Metrics tab all rendering with wrong or missing styles despite forge-test.sh being fully green.

**Root cause chain:**
1. No Tailwind is installed in this project (no tailwind.config.*, no postcss.config.*, tailwindcss not in package.json) yet ~9 files still write `className="rounded-md border-[var(--color-border)] px-2 py-1 ..."`. Those class names are inert.
2. Many components reference global class names (`.settings-layout`, `.metrics-page`, `.kpi-grid`, `.btn`, `.dialog-overlay`, `.theme-cards`) that are not defined in globals.css / theme.css / tokens.css — no matching CSS module either.
3. Files also use CSS variables (`--color-border`, `--color-surface`, `--color-danger`, `--color-success`, `--color-surface-hover`, `--space-16`) that were never added to tokens.css.
4. BFF /runs/{id}/events returned raw agent-server events without a `.summary` field, so EventCard displayed only icon + timestamp for every message.
5. BFF had no /runs/{id}/metrics endpoint, so the Metrics tab's fetch 404'd and the component sat on `loading` skeletons (Banner didn't render because bffGet's error path was masked by refetchInterval).

**Fix:** Wrote src/styles/legacy-globals.css to define every missing class name + a minimal Tailwind-atom shim, added compat aliases and missing spacing tokens to tokens.css, added `bff/services/event_normalize.py` (piped into GET /runs/{id}/events), added `bff/services/run_metrics.py` + GET /runs/{id}/metrics endpoint, and rewrote WorkspaceCard buttons to use the new `.btn` classes.

**Files touched:** src/styles/{legacy-globals.css (new),globals.css,tokens.css}, bff/services/{event_normalize.py,run_metrics.py} (new), bff/routers/runs.py, src/components/domain/WorkspaceCard.tsx
