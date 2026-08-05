# Scoring Bundle — 20260805_0726 UTC

Cells present: 11/11
Cells missing: (none)

## Gold Answers
### GOLD — debug

[gold/debug.md MISSING]

### GOLD — arch

[gold/arch.md MISSING]

### GOLD — plan

# Gold Answer — plan.txt

Forge-OH Step 3 atomic-commit plan. Real conversation create + WebSocket relay + live event timeline. Produced by Model Council v2 (Claude Fable 5 + GPT 5.6 Sol + Gemini 3.1 Pro, 2026-08-05).

Council members and their reports:
- Claude Fable 5 (`/home/user/workspace/model-council-claude_fable_5.md`)
- GPT 5.6 Sol (`/home/user/workspace/model-council-gpt_5_6_sol.md`)
- Gemini 3.1 Pro (`/home/user/workspace/model-council-gemini_3_1_pro.md`)

Full synthesis: `/home/user/workspace/model-council-synthesis.md`.

## The 9-Commit Plan

1. **Remove `bff/services/openhands_client.py` shim; canonical client is `bff/openhands_client.py`**
   - Files touched: `bff/services/openhands_client.py` (delete)
   - Rationale: Resolves the backend duplicate before any Step 3 code exists, so commits 5–9 can only import the canonical `bff.openhands_client.get_client`. Verified zero importers of the shim path at baseline (via `git grep`), so this is a pure deletion with no import fixes; trivially boots.

2. **Remove `src/lib/hooks/useRunStream.ts` duplicate and its two stale unit tests**
   - Files touched: `src/lib/hooks/useRunStream.ts`, `src/tests/unit/useRunStream.test.ts`, `src/tests/unit/useRunStream-stale-closure.test.ts` (all delete)
   - Rationale: Run-detail imports `@/lib/streaming/useRunStream`, so the hooks copy is dead code; deleting the hook and its tests together honors the "no new tests" constraint (nothing is written) and guarantees all later streaming work happens in one surviving file.

3. **Fix `BFF_WS` default from port 8000 to 8081 in `src/lib/streaming/socket.ts`**
   - Files touched: `src/lib/streaming/socket.ts`
   - Rationale: `useRunStream` connects to `BFF_WS`, which defaults to a port nothing listens on — landing this before the relay exists prevents the first relay smoke test from being confounded by a silent connect-to-nowhere (the exact failure mode historical fix `32fa5d9` addressed).

4. **Rename composer form field `contextPrompt` → `taskPrompt` in the run composer**
   - Files touched: `src/components/domain/NewRunComposer.tsx`
   - Rationale: Composer sends `contextPrompt` at baseline; backend's `POST /runs` reads `body.taskPrompt`. Without this rename the entire pipeline can be wired correctly and the agent still receives an empty `initial_message` — a silent-failure trap.

5. **Add `bff/services/event_relay.py`: consume agent-server `/sockets/events` WS, forward to Socket.IO rooms**
   - Files touched: `bff/services/event_relay.py` (new)
   - Rationale: The riskiest new module lands **inert** (imported by nothing, so boot cannot break) with the correct browser contract baked in from day one — emit names `event` and `status` (not `oh-event`/`oh-status`; hotfix lesson #2), `runId` enrichment on every forwarded event, room key `conversationId=<cid>`, `start_relay(cid)`/`stop_relay(cid)`/`shutdown_all()` lifecycle, `resend_mode=all` on first connect and `resend_mode=since` on reconnect, consumed via `aiohttp.ClientSession.ws_connect` (aiohttp is already pinned in `bff/requirements.txt` — no new dependency).

6. **Wire Socket.IO connect/subscribe/unsubscribe handlers and relay lifecycle into `bff/main.py`**
   - Files touched: `bff/main.py`
   - Rationale: Activates the relay plumbing. Handlers join room `conversationId=<cid>` and call `start_relay(cid)`, accepting **both** `runId` and `conversationId` query params (hotfix lesson #3 — the frontend sends `?runId=<uuid>`). `event_relay.set_sio(sio)` wired at module scope and `shutdown_all()` added to lifespan. Depends on commit 5's module existing; independently verifiable by connecting a socket.io client and confirming room join with no crash.

7. **Wire `GET /runs` and `GET /runs/{run_id}` to agent-server conversation reads**
   - Files touched: `bff/routers/runs.py`
   - Rationale: Read path before write path. Uses `GET /api/conversations/search` — **not** bare `/api/conversations`, which is a batch-get-by-ids route that 422s without ids (hotfix lesson #1). Plus `GET /api/conversations/{id}` for the detail read. Translates `ConversationInfo → RunSummary` with status map: `idle → queued`, `running → running`, `paused → paused`, `waiting_for_confirmation → awaiting_approval`, `finished → succeeded`, `error/stuck/deleting → failed`. Deletes `"stub": True` from both reads. Testable right now by curl-creating a conversation directly against `:8090` and watching it render in the Runs list and run-detail header — the UI needs no changes.

8. **Proxy `GET /runs/{run_id}/events` to agent-server events search**
   - Files touched: `bff/routers/runs.py`
   - Rationale: Gives the run-detail timeline its historical-event backfill on page load/refresh (the live WS relay only covers events after subscribe). Proxies to `GET /api/conversations/{id}/events/search`. Deletes `"stub": True` from this endpoint. Verifiable against the curl-created conversation from commit 7 before any UI-driven run exists.

9. **Wire `POST /runs` to agent-server conversation create + run kickoff + event relay start** ← **keystone; first end-to-end pass**
   - Files touched: `bff/routers/runs.py`
   - Rationale: The write path lands last, when every consumer is already real. Keeps the existing `route_request()` call and its `status: "blocked"` short-circuit (form must reflect `queued`/`blocked` from real model routing). Translates the routed model to LiteLLM form (`openai/qwen3.6:35b-a3b` with `base_url` `http://localhost:11434/v1`). Sends `StartConversationRequest` with `initial_message.content[0].text = body.taskPrompt`, tools `terminal` / `file_editor` / `task_tracker` / `browser_tool_set`, and a `LocalWorkspace`. Then `POST /api/conversations/{id}/run` (tolerating 409 as already-running). Then `start_relay(cid)`. Deletes the final `"stub": True`. The moment this commit exists, submitting a task from the UI appears in the Runs list (commit 7), renders real status (commit 7), backfills history (commit 8), and streams live Action/Observation events over the relay (commits 3–6) — satisfying the "final commit = first e2e pass" constraint.

## Manual Verification After Commit 9

Submit a prompt from the composer → run appears in Runs list → open run-detail → timeline populates live → status transitions `queued → running → succeeded`.

Historical first run confirmed this exact flow green: qwen3.6:35b-a3b, 12,491 prompt tokens, `execution_status: finished` in ~8 s (per hotfix commit `78d525f`).

## Boot-Safety Audit (Why Every Intermediate State Runs)

| After commit | uvicorn boots because… | npm run dev because… |
|---|---|---|
| 1 | shim had zero importers | untouched |
| 2 | untouched | survivor is the only imported copy |
| 3 | untouched | one-line default change |
| 4 | untouched | one form field renamed to match backend contract |
| 5 | new module imported by nothing | untouched |
| 6 | imports commit 5's module (exists); handlers inert until a client connects | untouched |
| 7–8 | router edits only; agent-server-down path degrades to empty list/502, not crash | UI already calls these endpoints |
| 9 | write path added atop proven read path + relay | no frontend change needed |

## Out-of-Band Log Updates (Not Part of the 9 Code Commits)

Per project custom instructions, append `BUILD_LOG.md` slice entry and refresh `SESSION_HANDOFF.md` after manual verification. Deliberately outside the 9-commit sequence so the final code commit remains the e2e keystone.

## Contract Lessons Baked In (from Historical Hotfixes)

1. **List endpoint 422** — `GET /api/conversations/search` (paginated), NOT bare `/api/conversations` (batch-get by ids). Baked into commit 7.
2. **Socket.IO emit names** — `event` and `status`, NOT `oh-event`/`oh-status`. `useRunStream.ts` listens on `['run:event','message','event','status','approval_required','error']`. Baked into commit 5.
3. **Both `runId` and `conversationId` query params** — frontend sends `?runId=<uuid>`; server must accept both because `run_id == conversation_id` identity contract. Baked into commit 6.

## Sources

- OpenHands agent-server v1.40.0 conversation_router: https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-agent-server/openhands/agent_server/conversation_router.py
- OpenHands agent-server v1.40.0 sockets: https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-agent-server/openhands/agent_server/sockets.py
- Forge-OH historical monolith commit: https://github.com/rmholston420/Forge-OH/commit/be73943c1eededf8eedcfbf0654a196f36cc77c3
- Forge-OH post-run hotfix (three contract mismatches): https://github.com/rmholston420/Forge-OH/commit/78d525f76221547b54f87f005f32d7b20cf870ab
- Forge-OH poll-loop unblock hotfix: https://github.com/rmholston420/Forge-OH/commit/07a5c04
- Forge-OH port-default fix: https://github.com/rmholston420/Forge-OH/commit/32fa5d9


## Rubrics
### RUBRIC — debug

[debug rubric MISSING]

### RUBRIC — arch

[arch rubric MISSING]

### RUBRIC — plan

[plan rubric MISSING]

## Cell Responses
### CELL c01 — model=? runtime=vllm role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_014555_run/c01__arch.json`

### CELL c02 — model=? runtime=vllm role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_015155_run/c02__plan.json`

### CELL c03 — model=? runtime=ollama role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_013900_run/c03__debug.json`

### CELL c03b — model=? runtime=vllm role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_023732_run/c03b__plan.json`

### CELL c04 — model=? runtime=vllm role=planner
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_020003_run/c04__plan.json`

### CELL c05 — model=? runtime=vllm role=planner
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_021314_run/c05__plan.json`

### CELL c08 — model=? runtime=ollama role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_014107_run/c08__arch.json`

### CELL c09 — model=? runtime=vllm role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_024700_run/c09__arch.json`

### CELL c11 — model=? runtime=vllm role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_025748_run/c11__debug.json`

### CELL c12a — model=? runtime=vllm role=coder
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_030014_run/c12a__plan.json`

### CELL c12b — model=? runtime=vllm role=planner
Source: `/home/rmholston/.forge-oh/bench_pathE/20260805_030204_run/c12b__debug.json`
