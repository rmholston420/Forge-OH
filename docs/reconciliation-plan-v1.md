
# Forge-OH Reconciliation Plan v1

> **Status:** Canonical, authoritative execution plan for all Forge-OH work.
> **Supersedes** `Forge-OH-Action-Plan-v4.md` entirely as of 2026-08-05.
> Historical BUILD_LOG.md entries that reference v4 by name remain as
> append-only history — but no new work stages from v4.
> See `AGENTS.md` § Canonical Planning Documents.
>
> Companion / stage-specific docs live at `docs/reconciliation-plan-stage-*.md`
> (e.g. `docs/reconciliation-plan-stage-1H.md`).

Standalone implementation plan for Perplexity Computer. Target: Colossus (128GB RAM, RTX 5090, 32GB VRAM, Blackwell SM_120). Single-user, local-first. Graph store: DozerDB (no Neo4j/DozerDB debate — DozerDB is settled). Governing rule for every stage below: **backend and frontend ship together in the same commit/session. A backend endpoint with no UI path, or a UI control with no real backend effect, is not "done."**

Source basis: `ideal-ACA-v8.md` (target architecture) reconciled against `forge-oh-improvement-plan-v2.md` (current-state remediation plan, governing rule origin).

Logging discipline (continuous, not deferred):
- `BUILD_LOG.md` — one entry per completed stage, append-only, timestamped, noting backend files touched, frontend files touched, and explicit confirmation both halves shipped.
- `DEBUG_LOG.md` — one entry per defect at time of diagnosis (even before fixed), append-only.
- `PORTING_LEDGER.md` — one entry per vendored/ported component at commit time: source URL, commit hash/tag/ADR number, SPDX license or same-owner note, modification notes.
- `SESSION_HANDOFF.md` — overwritten (not appended) at end of each session: current stage, what's done on both halves, what remains, exact next action.

Before starting any stage: read `SESSION_HANDOFF.md` if it exists. Before investigating any new error: search `DEBUG_LOG.md` for a matching symptom first.

---

## Stage 1 — Make Forge-OH Functional (Bootstrap Tool)

**Goal:** clean install + minimum backend/frontend pairs so Forge-OH itself can be used to build every later stage. Nothing downstream is verifiable until this stage is done.

### 1.1 Fix install blockers
- Pin/relax the `lmnr` vs `openhands-sdk` transitive dependency conflict (likely `httpx`/`pydantic` inside `lmnr`).
- Regenerate `requirements.lock` so it pins `openhands-sdk==1.40.0` (not the stale `1.29.3`).
- Rename `package.json` scripts to match `.github/workflows/ci.yml` (`typecheck`, `test:unit`).
- Verify:
  ```
  pip install -r bff/requirements.txt -r bff/requirements-dev.txt
  pytest bff/tests/ --collect-only
  grep openhands-sdk requirements.lock
  pnpm typecheck && pnpm test:unit
  ```
  All must exit 0 / show 0 collection errors / show `1.40.0`.

### 1.2 Wire MCP Tools page (real backend + real frontend, currently disconnected)
- Replace the permanent `EmptyState` stub in `app/(dashboard)/tools-mcp/page.tsx` with `features/mcp/McpPage.tsx`.
- Fix the missing `/api` prefix bug in `features/mcp/api.ts`: `${BASE}/mcp` → `${BASE}/api/mcp`.
- Verify: register a real MCP server through the UI, confirm ping/toggle/delete round-trip against the live BFF.

### 1.3 Secrets nav entry + stub deletion
- Add a `/secrets` entry to `Sidebar.tsx`.
- Delete the redundant "coming soon" stub after removing inbound links.

### 1.4 Safe dead-code deletions (parallelizable with 1.2–1.3)
- Delete the 12 unused `src/app/api/*` proxy routes (wrong URL shape, unvalidated `x-forge-token` header).
- Delete `src/lib/plugins/hooks.ts` and its dead `PluginsPage.tsx`.
- Delete `src/lib/runs.ts` (response shape doesn't match the real BFF shape).
- Delete the dead `FEATURE_RIGPA_LMS_ENABLED` var from `docker-compose.yml`.
- Delete the `TODO(foh-phase2): delete this file` markers in `bff/routers/agents.py`, `notifications.py`, `mcp-server-card.tsx`.
- Confirm zero-importer grep result for each before deleting.

### 1.5 Agent Presets — full stack
- Frontend: swap the stub for `features/agent-presets/AgentPresetsPage.tsx`.
- Backend: replace the cloud-model `Literal` (`gpt-4o`, `claude-opus-4`, etc.) on `AgentPreset.model` with real local Ollama/vLLM tags sourced from `bff/services/model_router.py`.
- Backend: fix `create_run` so `agentPresetId` actually drives `route_by_role()` and the `agent` block sent to agent-server, instead of being echoed cosmetically as `agentPresetName`.
- Persistence: move `_PRESETS` from an in-memory dict to a SQLite table, consistent with the existing `episodic_memory.db`/`trajectories.db` pattern.
- Verify: create a preset with a real local model, start a run selecting it, confirm the response's `routing` block shows the preset's model was actually used, confirm the preset survives a BFF restart.

### 1.6 Send Message While Running (highest daily-use impact)
- Backend: add `POST /runs/{run_id}/message`, forwarding `{role: "user", content: [...], run: true}` to agent-server's `POST /api/conversations/{cid}/events`.
- Frontend: persistent message composer on the run-detail page, enabled whenever status is RUNNING, PAUSED, or WAITING_FOR_CONFIRMATION, wired via `features/run-detail/api.ts` following the existing `pauseRun`/`resumeRun` pattern.
- Verify: send a message mid-run, confirm the agent receives and reacts to it without stopping/forking.

### 1.7 Fix dead Socket.IO `approval_required` listener
- `useRunStream.ts` already listens for `approval_required`; the BFF never emits it. Add ~15 lines to `event_relay.py` to emit `approval_required` on the `waiting_for_confirmation` transition.
- Reconcile the `SOCKET_EVENTS` registry and its self-referential test against the BFF's actual `_emit()` call sites.
- Verify: trigger a confirmation-required action, confirm the UI updates via push, not polling.

**Stage 1 exit criteria (all required before Stage 2):** 1.1, 1.2, 1.5, 1.6 verified clean. Log each item in `BUILD_LOG.md` as it lands; log Tier 0 defects in `DEBUG_LOG.md` at diagnosis time.

---

## Stage 2 — Inference-Backend Flexibility (`ModelClient` Port)

### 2.1 Backend: `InferenceBackend` protocol
- Extend `model_router.py` with a protocol: `base_url`, `health_check()`, `list_models()`, `supports_streaming`.
- Implement four adapters: `OllamaBackend`, `VLLMBackend`, `LlamaCppBackend`, `SGLangBackend`, all behind the same OpenAI-compatible client interface currently used for Ollama.
- Add `GET /api/inference-backends` (list configured backends + live health).
- Extend `POST /runs` routing payload to accept `backendId` alongside `agentPresetId`.

### 2.2 Frontend: backend selector
- Add a backend selector (Ollama / vLLM / llama.cpp / SGLang) to the Agent Presets editor and run-creation form.
- Show live health/reachability per option, reusing the `MCPServerCard` Connected/Warning/Disconnected badge pattern.

### 2.3 Colossus-specific adapter tuning (lives in the adapter, never the core)
- llama.cpp: `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="120" -DGGML_CUDA_FA_ALL_QUANTS=ON`.
- vLLM: `TORCH_CUDA_ARCH_LIST="12.0"`, PyTorch cu128/cu130, FlashInfer attention backend (not `flash-attn`, which throws `undefined symbol` on SM_120).
- CUDA 12.8+ (13.2 + cuDNN 9.20 recommended); do not mix CUDA 12 install with newer PyTorch Blackwell wheels.
- Auto-select quant tier at process start by querying VRAM/compute capability (`nvidia-smi`): 32B-class at Q8 full-context, or 70B-class at IQ3/Q4_K_M within the 32GB budget.

### 2.4 Bound worktree-agent concurrency by VRAM
- Compute actual VRAM budget (base model footprint + per-concurrent-request KV cache at configured context length) as a runtime-read value from the hardware-detection adapter, not a hardcoded constant.
- Cap active-worktree-agent count at whatever concurrency fits with headroom for sandboxed tool-execution processes on the same GPU.

### 2.5 Verify
- Start a run against each of the four backends in turn (pull/serve a small test model on each).
- Confirm `model_router.py` routes correctly per selection.
- Confirm the frontend selector reflects real-time health for all four.

---

## Stage 3 — Security, Risk, and Approval Maturity

### 3.1 Security Analyzer risk indicators
- Backend: confirm whether pinned `openhands-sdk==1.40.0` exposes security-analyzer risk scores on `ActionEvent`s; if present, surface `risk_level` in `event_normalize.py`'s action mapping.
- Frontend: risk badge (low/medium/high) next to actions in the event timeline and terminal/command views, with an option to auto-collapse low-risk actions.
- Do not ship the backend field without the badge.

### 3.2 Policy-based confirmation (depends on 3.1's risk data)
- Backend: extend `requireApproval: bool` into `confirmationPolicy: {mode: "risk_based"|"all"|"none", threshold: "medium"}`, forwarded to agent-server's existing `confirmation_policy` support.
- Frontend: extend run-creation form and Agent Presets with a confirmation-policy selector replacing the single checkbox.

### 3.3 `DependencyGuard` port (new — closes an ACA-v8 gap absent from prior Forge-OH planning)
- Backend: deterministic pre-install check (not an LLM judgment call) querying PyPI/npm metadata API for package existence, publisher identity, and registration date before any agent-initiated install.
- Flag any package registered within the prior 30-90 days for human review.
- Enforce lockfile hash pinning (`requirements.txt`/`package-lock.json`) verified in CI.
- Off-allowlist packages block on human approval, routed through the existing `NotificationChannel`/approval-gate port — never auto-install.
- Frontend: approval surface for flagged/off-allowlist packages, reusing the existing HITL approval UI pattern.
- Invoke this as a pre-install hook in the `Implement`-phase task queue.

### 3.4 GPU thermal-hook staleness fix
- Backend: add `last_poll_ts` field to `/api/gpu` snapshot response.
- Consumer: have the GPU hook check staleness against it and log a visible WARNING (still fail open per documented safety philosophy, but make it visible).

### 3.5 Compare-endpoint contract fix
- Fix `ENDPOINTS.RUNS.compare` to match backend's real `?base=&fork=` contract (frontend currently builds `?left=&right=`). Grep for callers first — none confirmed yet.

---

## Stage 4 — RepoGraph + Code Intelligence (LSP Tier)

### 4.1 Enable RepoGraph for real (ops)
- Confirm DozerDB is live and reachable for RepoGraph's tree-sitter/symbol extraction workload (see consolidation note below).
- Populate the DozerDB connection credentials referenced in the driver's warning log.
- Flip `repograph_enabled` from hardcoded `False` to env-driven (`REPOGRAPH_ENABLED=true`).
- Verify: `GET /api/repograph/health` returns `available: true` instead of 503.

### 4.2 Graph-shaped aggregation endpoint (backend)
- New `openhands_tools_ext/repograph/store.py::full_graph(repo_key, limit=500)` — single Cypher-equivalent query returning symbol nodes (pagerank, category, rel_path) and CALLS/DEFINES edges, capped by pagerank for large repos.
- New `GET /api/repograph/graph?repo_key=...&limit=500` returning `{nodes, links}` in the exact shape `ForceGraph2D` expects.

### 4.3 Visualization component (frontend — ships in the same pass as 4.2)
- Vendor `react-force-graph-2d` (MIT, Canvas-based). Log in `PORTING_LEDGER.md` with source URL, pinned version, SPDX license.
- New `RepoGraphGraphView.tsx`: nodes colored/sized by pagerank, click-to-drill into existing `useCallers`/`useCallees` hooks.
- Add a List/Graph toggle inside the existing `RepoGraphPanel.tsx`.
- Add a standalone `/repograph` top-level route + sidebar entry for whole-codebase exploration (in addition to the per-run Trace-tab panel).

### 4.4 `LSPClient` port (new — closes an ACA-v8 gap)
- Backend: wrap Serena (MCP-exposed, wraps standard language servers) to expose "go to definition," "find all references," safe symbolic renames. Register as an MCP tool. Lazy-start language servers only for languages present in the active worktree.
- Frontend: expose LSP tool calls as a distinct event-card type in the run-detail timeline, matching the existing `ToolAction`/`Observation` variant pattern.
- Retrieval tiering to enforce going forward: Tier 1 grep/ripgrep (near-zero cost, broad search) → Tier 2 tree-sitter + embeddings (semantic fallback) → Tier 3 LSP (symbol-precise operations only, invoked when the task genuinely needs symbolic guarantees).

**Decision point before Stage 5 — resolve, do not assume:** DozerDB is the settled graph store. Confirm whether RepoGraph's symbol graph and Stage 5's semantic-memory temporal graph run on the *same* DozerDB instance or separate containers. Recommend consolidating onto one instance unless RepoGraph's PageRank queries and Graphiti's temporal index prove to need isolation under load. Flag for explicit sign-off before Stage 5 begins.

---

## Stage 5 — Four-Tier Memory Port (Kosmos → Forge-OH, on DozerDB)

### 5.1 Port pure interfaces
- Port `ports/memory.py`, `ports/vector.py`, `ports/embeddings.py` verbatim — no Kosmos-specific coupling.

### 5.2 Port concrete adapters
- Port `adapters/vector/qdrant/adapter.py` (`QdrantVectorAdapter` + `QdrantBackend` Protocol seam + `InMemoryQdrantBackend` test fake).
- Port `adapters/embeddings/ollama/adapter.py` (`OllamaEmbeddingsAdapter`, native `/api/embed`, `nomic-embed-text` default) — targets the same Colossus Ollama instance already in use, no new inference dependency.

### 5.3 Port DozerDB-native semantic path
- Port `adapters/memory/dozerdb/semantic_memory_path.py` and the `search_semantic()` implementation from ADR-074 — this adapter is already DozerDB-native, so only import-path and tool-registration adaptation is required, no store-migration decision.

### 5.4 Infra
- Add a Qdrant service to `docker-compose.yml` alongside the DozerDB service from Stage 4.

### 5.5 Zero-trust write enforcement (port-layer, non-bypassable)
- `upsert()`/`write_event()` raise on missing `provenance` or an out-of-range `confidence` float, enforced at the port layer for every caller including trusted internal plugins.

### 5.6 ACE-style memory curation
- Once Letta-style self-editing memory blocks are wired on top of the ported memory port, memory-block edits follow generation → reflection → curation, not ad-hoc overwrite.

### 5.7 Frontend exposure (mandatory)
- Surface which memory tier(s) were consulted per agent planning step in the run-detail timeline (extends Stage 6.2's condensation-visibility work).
- Add a memory-inspector view (Skills page tab, or its own settings/observability tab) showing recent `write_event`/`search_semantic` calls with `provenance` and `confidence` visible, reusing the masked-but-inspectable `SecretRow` pattern.

### 5.8 Verify
- Write a memory event with missing `provenance`; confirm rejection at the port layer (not just logged).
- Confirm `search_semantic()` returns real Qdrant-ranked hits against live Colossus Ollama.
- Confirm the frontend inspector surfaces the write with provenance/confidence visible.

### 5.9 Porting ledger
- Log in `PORTING_LEDGER.md`: source repo `rmholston420/kosmos`, file paths (`ports/memory.py`, `ports/vector.py`, `ports/embeddings.py`, adapter paths), ADR numbers (021, 026, 027, 073, 074), note as same-owner internal port.

---

## Stage 6 — Harness Engineering Upgrades

### 6.1 Ported SearXNG web-research tool (Kosmos `SearchPort`, do not rebuild)
- Port `ports/search.py` (Protocol, `SearchResult`/`SearchResponse` dataclasses, mandatory `provenance` field, keyword-only `search(query, *, num_results, language, engines)`).
- Port `adapters/search/searxng/adapter.py` (JSON-first with HTML-fallback parser) and its contract test.
- Deploy local SearXNG via Docker Compose.
- Backend: wrap as an `openhands_tools_ext` tool, thin call to `SearchPort.search()`.
- Frontend: distinct event type in run-detail timeline (following the `EventCard` `Type` variant pattern) showing query issued, source list with links, `provenance` strings.
- Optional follow-up (defer): promote to a delegated research sub-agent via OpenHands agent-delegation, porting Kosmos's Zetesis research-loop modules (`claim_support.py`, `cove.py`, `rubric_critique.py`, `self_consistency.py`).
- Verify: issue a task requiring current external info, confirm the agent calls the tool, confirm SearXNG returns real results, confirm provenance is visible in the UI.

### 6.2 Condensation visibility
- Backend: give `CondensationEvent`/`CondensationSummaryEvent` their own normalized type in `event_normalize.py` instead of falling through to generic `"status"`.
- Frontend: render a collapsible "context compressed — N turns summarized" marker in the timeline.

### 6.3 Idempotency ledger (new — closes an ACA-v8 durable-execution gap)
- SQLite-backed table keyed by `task_id + step_index + argument_hash`.
- Every state-changing tool call checks for a prior completion record before re-issuing the call on replay/resume — closes the exactly-once gap that checkpointing alone doesn't solve (checkpointers save state between nodes, not inside one).

### 6.4 Checkpoint-to-disk revert (new — closes an ACA-v8 gap)
- Backend: UI-triggered action that reverts conversation state and working-directory contents atomically to a selected checkpoint (`git reset --hard` to the associated commit + state restore).
- Frontend: revert control on the checkpoint/history view, composed with the existing `Conversation.fork()` mechanism.

### 6.5 Runtime model switching
- Backend: `POST /runs/{run_id}/model` forwarding to agent-server's `switch_model` — confirm the exact REST equivalent exists at pinned SDK 1.40.0 before committing (doc reference may be SDK-level test only, not a confirmed REST surface).
- Frontend: model-switch control in run-detail header, reusing `ModelSection.tsx`'s picker pattern.
- Do not ship the backend endpoint if the frontend control is deferred.

### 6.6 Skills/Microagents management page
- Backend: `GET /api/skills` proxy if agent-server exposes a skills-listing endpoint at pinned version; otherwise read skill definitions from disk.
- Frontend: new `/skills` page listing skills and trigger conditions, plus surfacing which skills fired on a given run in that run's Trace tab (using `event_normalize.py`'s `activated_skills` field).

### 6.7 Code-execution-with-MCP invocation mode
- For tool-heavy phases (multi-file edits, multi-step verification): default to the agent writing code that calls tools programmatically rather than loading full tool-definition schemas into context every turn.
- Fall back to direct MCP calls only for single, simple invocations where code-execution overhead isn't justified.
- Pair with progressive disclosure: load only tool/skill name + one-line description at session start; load full schema only once the current task is identified as needing that specific tool.

---

## Stage 7 — Infra Cleanup and Deferred Items (last, no runtime impact on Colossus dev flow)

### 7.1 Docker Compose reconciliation
- Rewrite `docker-compose.yml` to match the real single-host topology: containerize `bff` + `frontend` + DozerDB (Stage 4) + Qdrant (Stage 5); run agent-server as a host process per the documented `forge-up.sh` path.
- Fix the nonexistent `Dockerfile.frontend` reference.

### 7.2 Healthcheck fix
- Add a real `src/app/api/health/route.ts` returning `{ok: true}`; point the Dockerfile healthcheck at it.

### 7.3 Remove `next-auth` vestige
- Strip the `next-auth` dependency and `NEXTAUTH_SECRET`/`NEXTAUTH_URL` CI env vars together — auth is explicitly out of scope for this single-user local system.

### 7.4 Webhook subscriber
- Backend: minimal `bff/services/webhook_dispatcher.py` posting to a configurable local URL on `FINISHED`/`ERROR`/`WAITING_FOR_CONFIRMATION` transitions, reusing existing `event_relay.py` transition-detection.
- Frontend: settings field to configure the target URL.

### 7.5 VSCode / VNC / live browser takeover
- Lowest ROI, largest integration effort. Backend: proxy agent-server's VSCode/VNC/browser session URLs through the BFF, reusing the existing MCP passthrough auth pattern. Frontend: new embedded iframe tabs alongside Trace/Terminal/Files.
- Build both halves as one unit; defer until all prior stages are functional.

### 7.6 Explicitly deferred (real ACA-v8 items, no current dependency chain forcing them)
- Local LoRA/QLoRA fine-tuning path (Axolotl/Unsloth, Blackwell FP4/NVFP4 tensor-core support).
- MLflow champion/challenger evaluation harness.
- Langfuse tracing.
- Voice I/O (whisper.cpp/Piper).
- Revisit these based on actual need after Stage 6, not spec completeness.

---

## Recommended Execution Order (single-session-sized chunks)

1. Stage 1.1 → 1.2/1.3/1.4 (parallel) → 1.5 → 1.6 → 1.7
2. Stage 2.1–2.5 in sequence
3. Stage 3.1 → 3.2 → 3.3 → 3.4/3.5 (parallel)
4. Stage 4.1 → 4.2+4.3 (same pass) → 4.4 → resolve DozerDB consolidation decision
5. Stage 5.1 → 5.2 → 5.3 → 5.4 → 5.5 → 5.6 → 5.7 → 5.8 → 5.9
6. Stage 6.1 → 6.2 → 6.3 → 6.4 → 6.5 → 6.6 → 6.7
7. Stage 7.1–7.5 in any order, 7.6 deferred indefinitely pending need

Never advance to the next numbered stage with an unresolved backend-only or frontend-only half from the current stage.
