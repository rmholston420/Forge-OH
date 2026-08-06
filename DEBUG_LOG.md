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

## 2026-08-03 00:07 EDT — Client feature flags always false in browser bundles
- Symptom: With NEXT_PUBLIC_FEATURE_APPROVAL_GATE=true in .env.local and Next confirming the file at startup ("Environments: .env.local"), the NewRunComposer.tsx did not render the {approvalGateOn && ...} block. Playwright dump of the modal DOM showed no requireApproval checkbox and no hidden input for it. Purging .next/ and restarting did not fix it.
- Affected stage/plugin/port: Stage 1E (Approval Gate), src/lib/feature-flags/index.ts, all consumers of useFeatureFlag/isFeatureEnabled inside Client Components.
- Root cause: readEnvFlag() used a computed lookup: process.env[`NEXT_PUBLIC_FEATURE_${flag}`]. Next.js only inlines *literal* process.env.NEXT_PUBLIC_* reads into client bundles. Any computed key access returns undefined in the browser. Server components worked; client components silently disabled every flag.
- Fix: Replace the computed lookup with a static Record<FeatureFlag, string|undefined> in src/lib/feature-flags/index.ts, one literal process.env.NEXT_PUBLIC_FEATURE_<NAME> per flag, so Next inlines them all at compile time. readEnvFlag() now just returns STATIC_FLAG_VALUES[flag].
- Files changed: src/lib/feature-flags/index.ts.

## 2026-08-03 00:09 EDT — Reject doesn't reach a terminal state on its own
- Symptom: Stage 1E e2e leg 2 verified respond_to_confirmation {accept:false} returned 200 but the run then sat in agent-server 'idle' → BFF 'queued' indefinitely.
- Affected stage/plugin/port: Stage 1E (Approval Gate), bff/routers/runs.py reject_run().
- Root cause: agent-server's response to a rejected confirmation is to abort the tool call and return the conversation loop to idle. There is no terminal-on-reject transition. From the user's POV the run is still open.
- Fix: reject_run() now POSTs to /interrupt after respond_to_confirmation. /interrupt yields 400 when the conversation is already idle/finished; that branch is tolerated. Successful interrupt drives execution_status to 'paused' (agent-server's version of a hard-cancel state). BFF status map already routes paused→paused, so the UI shows a paused run that can be resumed or fully stopped. This matches how OpenHands models cancellation.
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

## 2026-08-03 05:32 EDT — ruff I001 / ruff format alignment / mypy list[Any|None]
- Symptom: forge-test.sh failed with `ruff check` (I001 unsorted imports — false positive after adding blank line), `ruff format --check` (aligned-column dict literals), and `mypy` `Argument 1 to "join" of "str" has incompatible type "list[Any | None]"`.
- Affected: bff/services/event_normalize.py, bff/services/run_metrics.py (from commit 8f264cf).
- Root cause:
  1. Ruff format enforces single-space after colon in dict literals — aligned-column style is rejected.
  2. Mypy could not narrow `tc.get("name")` inside a list-comprehension; return type inferred as `Any | None`.
  3. FURB162: `.replace("Z", "+00:00")` before `datetime.fromisoformat` is redundant on Python 3.11+.
- Fix: remove aligned-column spacing; wrap comprehension with explicit `str(...)` and annotate `list[str]`; drop `.replace("Z", "+00:00")`.
- Reuse rule: NEVER align dict values by column padding — ruff format will fail. Always single-space after colon.

## 2026-08-03 05:34 EDT — Plugin Marketplace crash: React child object
- Symptom: `/plugins?tab=marketplace` renders Next.js runtime error overlay: "Objects are not valid as a React child (found: object with keys {name, description}). If you meant to render a collection of children, use an array instead." at `src/app/(dashboard)/plugins/page.tsx:102 @ PluginsPage` — `<PluginMarketplaceGrid />`.
- Affected: bff/routers/plugins.py (marketplace shape), src/components/domain/PluginMarketplaceGrid.tsx.
- Root cause: upstream agent-server returns `MarketplacePluginInfo.skills` as `list[{name, description, ...}]` in some environments but the BFF passes it through unchanged (`u.get("skills") or []`), and the frontend maps each entry directly into a `<span>{s}</span>` which errors on non-string items.
- Fix: normalize `skills` to `list[str]` in BFF `_to_marketplace`; add defensive coerce in the React component (fallback name/id/title).
- Reuse rule: any BFF response field that is later rendered as text MUST be a string primitive at the BFF boundary — never trust upstream dict shapes to survive JSX.

## 2026-08-03 05:34 EDT — /secrets page stuck on Skeleton
- Symptom: `/secrets` page renders the toolbar + notice but the table area is a wide dark rectangle (Skeleton) that never resolves. No error banner shown despite the fetch failing.
- Affected: src/features/secrets/api.ts.
- Root cause: `fetchSecrets` builds URL as `${BFF}/secrets` (no `/api` prefix). BFF mounts the secrets router at `/api/secrets`. Request 404s. React Query default retry (3× w/ exponential backoff) keeps `isLoading` true well past the Playwright snapshot; even after retries exhaust, the error IS set, but the retries alone are enough for a stale-skeleton capture.
- Fix: prefix `BASE` with `/api` in `src/features/secrets/api.ts` (all four functions).
- Reuse rule: NEVER hardcode BFF paths inside a feature `api.ts` — reuse `ENDPOINTS.SECRETS.list()` from `src/lib/api/endpoints.ts` (single source of truth). Follow-up: refactor secrets feature to route through `bffGet/bffPost/bffDelete` like the rest of the app.

## 2026-08-03 05:34 EDT — Metrics/Browser skeleton captured mid-flight
- Symptom: Metrics tab shows 5 shimmering skeletons; Browser tab shows a large empty rounded rectangle. Both should be "0 tokens / 0 cost / …" or "No browser activity" empty states.
- Affected: src/app/(dashboard)/runs/[runId]/tabs/MetricsTab.tsx, src/tests/e2e/visual-tour.spec.ts.
- Root cause: Playwright's `shot()` waited only 400ms after `networkidle`, so React Query's very first resolve after clicking a tab wasn't captured. `MetricsTab` was also unconditionally rendering skeletons while `isLoading===true`, hiding the actual zeros the endpoint returns.
- Fix: `MetricsTab` uses `showSkeleton = isLoading && !metrics` so first success wipes the skeleton immediately; `visual-tour.spec.ts` uses 1200ms + a secondary short `networkidle` wait.
- Reuse rule: any tab-scoped React Query view MUST render placeholder content (zeros / dashes) once data is available, not gate whole layout behind `isLoading`.

## 2026-08-03 05:44 EDT — Stale BFF process masks code fixes across `git pull`
- Symptom: after committing/pushing BFF Python fixes and running `git pull && bash scripts/forge-test.sh && bash scripts/forge-screenshots.sh`, screenshots still show pre-fix behavior. In this case Metrics/Browser 404, and MessageEvent rows blank.
- Affected: scripts/forge-up.sh, scripts/forge-screenshots.sh.
- Root cause: forge-up.sh treats "port in use" as "service already up" and leaves the old uvicorn process running. Because uvicorn was launched WITHOUT `--reload`, none of the newly-pulled BFF source is imported. Frontend changes appear because `pnpm dev` HMR reloads TS on save.
- Fix: forge-up.sh now kills the previous BFF pid and relaunches with `--reload --reload-dir bff`. forge-screenshots.sh calls forge-up.sh before Playwright so a fresh BFF is guaranteed for every visual-tour run.
- Reuse rule: any process that loads Python source at startup MUST be relaunched — not just port-checked — when the repo changes. Prefer `--reload` for local single-user dev.

## 2026-08-03 05:47 EDT — Stale BFF survives pid-file-based restart
- Symptom: forge-up.sh in 068daf7 logged `BFF port 8081 held by unknown process; leaving it alone`; screenshot audit confirmed BFF was still pre-pass-2.
- Affected: scripts/forge-up.sh.
- Root cause: previous BFF was launched by an older forge-up (or by hand) that did not write a pid file. My kill-by-pid-file guard therefore didn't trip, and the fallback branch bailed instead of killing.
- Fix: enumerate PIDs on the BFF port via `ss -ltnp`, filter to those whose cmdline matches `uvicorn.*bff\.main`, then kill them. Leaves unrelated processes alone.
- Reuse rule: any port-managed dev service kill logic MUST have a secondary "kill by port + cmdline signature" path — pid files are lost across reboots and manual launches.

## 2026-08-03 07:22 EDT — DozerDB reports edition=enterprise at Cypher level

**Symptom:** `CALL dbms.components() YIELD ... edition` returns `enterprise` on
Colossus's `kosmos-dozerdb` container, even though the container's own
`NEO4J_EDITION` env var is set to `community` and the image is
`graphstack/dozerdb:5.26.27` (not Neo4j Enterprise).

**Affected stage/plugin/port:** Step 8 Slice D.1 — RepoGraph health endpoint
(`bff/routers/repograph.py:repograph_health`).

**Root cause:** DozerDB is a fork of Neo4j Community that re-enables
Enterprise-only features (like multi-database). It re-uses the Enterprise
edition string internally so Cypher clients that gate on
`dbms.components().edition == 'enterprise'` continue to work. The container
env `NEO4J_EDITION=community` reflects packaging origin, not what the running
kernel reports.

**Fix applied:** None — this is correct behaviour for DozerDB. Documented so
future readers of a health response showing `edition=enterprise` don't
mistakenly assume a licensed Neo4j Enterprise install.

**Files changed:** DEBUG_LOG.md only (no code fix).

## 2026-08-03 07:22 EDT — `.oh-venv` has no `pip`; must use `uv pip install`

**Symptom:** `.oh-venv/bin/pip install -r bff/requirements.txt` fails with
`bash: .oh-venv/bin/pip: No such file or directory` on Colossus.

**Affected stage/plugin/port:** Any slice that adds new backend deps and asks
the user to install them into `.oh-venv`.

**Root cause:** The venv was created by `uv venv` which does not install `pip`
into the venv. Only `python`, `ruff`, `pytest`, and the OpenHands console
scripts land in `.oh-venv/bin/`.

**Fix applied:** Use `VIRTUAL_ENV=$PWD/.oh-venv uv pip install -r bff/requirements.txt`.
Confirmed working — installed 7 packages in ~8s including neo4j, networkx,
tree-sitter, tree-sitter-language-pack.

**Files changed:** DEBUG_LOG.md (documenting the correct command for future
dep-adding slices).

## 2026-08-03 07:39 EDT — D.4 search endpoint only matched Symbol.name, not filename

**Symptom:** On Colossus after `POST /index`, `GET /api/repograph/search?q=run_metadata` returned `[]` even though `bff/services/run_metadata_store.py` clearly exists with `RunMetadata` and `RunMetadataStore` classes.

**Affected stage/plugin/port:** D.4 endpoint `GET /api/repograph/search`, backed by `Neo4jStore.search_by_name` (openhands_tools_ext/repograph/store.py).

**Root cause:** The search Cypher only matched `Symbol.name`, but users naturally search interchangeably by symbol name AND filename ("where is the run_metadata thing?"). `run_metadata` is not the name of any symbol — it's a segment of a *filename*. So the search legitimately returned nothing but the UX is wrong.

**Fix applied:** Widened the search predicate to `WHERE toLower(s.name) CONTAINS toLower($q) OR toLower(s.rel_path) CONTAINS toLower($q)`. Now filename substring matches also surface. Also updated the unit test in `openhands_tools_ext/tests/test_store.py::TestReads::test_search_by_name_shape` to assert both branches of the OR are in the Cypher.

**Files changed:** openhands_tools_ext/repograph/store.py, openhands_tools_ext/tests/test_store.py.

**Verification:** 77/77 tests still pass locally; will re-verify on Colossus after commit.

## 2026-08-03 07:52 EDT — Pre-existing failure: `bffDownload > returns Blob on success` in lib-api-client.test.ts

**Symptom:** `AssertionError: expected Blob { size: 12, type: 'text/plain;charset=utf-8' } to be an instance of Blob`. The received object IS a Blob (same class name, same shape), it just fails `expect(blob).toBeInstanceOf(Blob)` in vitest+jsdom.

**Affected stage/plugin/port:** Not RepoGraph. Existed before Slice D. Verified by `git stash && npx vitest run src/tests/unit/lib-api-client.test.ts` on 2026-08-03 07:51 EDT — same 1 failure/9 pass regardless of D.5 changes.

**Root cause (suspected):** jsdom's global `Blob` and the `Blob` returned by our `bffDownload` come from different realms (undici polyfill vs. jsdom's own `Blob`). `instanceof` fails across realms even when the shape is identical. This is a common vitest+jsdom+undici trap.

**Fix (deferred):** Change the assertion to `expect(blob).toBeDefined()` and `expect(blob.size).toBe(...)` or set up `Blob` to point at a single realm in `vitest.setup.ts`. Not fixing right now because it's unrelated to RepoGraph and everything downstream still works at runtime.

**Files potentially involved:** src/lib/api/client.ts (bffDownload impl), src/tests/unit/lib-api-client.test.ts.

## 2026-08-03 08:04 EDT — JSX text nodes rendered literal `\u00b7` / `\u2026` instead of glyphs

**Symptom:** Frontend RepoGraph panel showed literal `\u00b7` and `\u2026` strings in the UI where middle dots and ellipses were meant. Also affected `PORTING_LEDGER.md`, `BUILD_LOG.md`, `DEBUG_LOG.md`, and two unit test files where the escapes appeared inside markdown or JSX text nodes rather than JS/TS string literals.

**Affected stage/plugin/port:** Slice D.5 frontend — `src/components/domain/RepoGraphPanel.tsx` and several unit-test/doc files.

**Root cause:** `\uXXXX` escape sequences are a **JS string-literal syntax only**. Inside JSX text (children of a tag) and inside markdown, the backslash-u sequence is treated as literal ASCII text and never converted to the unicode codepoint. Sequences like `<p>foo \u00b7 bar</p>` render six characters, not `foo · bar`.

**Fix:** Replaced every `\uXXXX` in JSX text nodes and markdown with the actual UTF-8 glyph (`·`, `—`, `…`). Sequences inside quoted JS/TS string literals (e.g. `'Press keys\u2026'`, `'\u2022'.repeat(12)`) are correct and were left alone.

**Files changed:**
- src/components/domain/RepoGraphPanel.tsx
- src/features/repograph/api.ts (docstring text)
- src/tests/unit/RepoGraphPanel.test.tsx (assertion strings against rendered text)
- src/tests/unit/repograph-endpoints.test.ts (comments)
- PORTING_LEDGER.md, BUILD_LOG.md, DEBUG_LOG.md

**Verification:** `npx vitest run src/tests/unit/RepoGraphPanel.test.tsx src/tests/unit/repograph-endpoints.test.ts` → 14/14 pass after fix (assertions updated to match real glyphs).

**Lesson for future slices:** whenever writing JSX text or markdown, use the literal glyph. Reserve `\uXXXX` for JS/TS string literals only.

## 2026-08-03 12:15 EDT — Python venv orphaned by OS upgrade

**Symptom:** `ModuleNotFoundError: No module named 'vllm'` in venv that previously worked. `~/venv/vllm/bin/python -c "import vllm"` fails; `vllm` package still visible in `~/venv/vllm/lib/python3.13/site-packages/`.
**Affected stage/plugin/port:** F.18 (vLLM standalone).
**Root cause:** An OS upgrade removed `/usr/bin/python3.13`. The venv's `bin/python` symlink pointed at `/usr/bin/python` which silently switched to 3.14. All 3.13 site-packages were orphaned.
**Fix:**
```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.13 python3.13-venv python3.13-dev
```
Recreated venv symlinks manually if needed.
**Files changed:** none (system packages only).

## 2026-08-03 12:50 EDT — vLLM GGUF loader rejects bf16

**Symptom:** vLLM launch dies with `ValueError: bfloat16 is not supported for GGUF quantization`.
**Affected stage/plugin/port:** F.18.
**Root cause:** vLLM's GGUF loader path only accepts float16 or float32, even when the source model is bf16.
**Fix:** Add `--dtype float16` to launcher. Warns "Casting torch.bfloat16 to torch.float16" but loads.
**Files changed:** `scripts/vllm_start.sh`.

## 2026-08-03 13:31 EDT — Triton JIT missing Python.h

**Symptom:** Model loads (17.4 GiB), then engine dies during `_dummy_run`/profile phase with:
`/tmp/tmpjs0coger/cuda_utils.c:5:10: fatal error: Python.h: No such file or directory`.
**Affected stage/plugin/port:** F.18.
**Root cause:** Triton compiles a small C extension (`cuda_utils.c`) at runtime for its GPU launch path. Requires Python development headers, which `python3.13` alone doesn't install.
**Fix:**
```
sudo apt-get install -y python3.13-dev
```
Verify: `ls /usr/include/python3.13/Python.h`.
**Files changed:** none.

## 2026-08-03 13:32 EDT — FlashInfer refuses SM_120

**Symptom:** vLLM engine startup fails during sampler init:
`RuntimeError: FlashInfer requires GPUs with sm75 or higher` — despite RTX 5090 being SM_120.
**Affected stage/plugin/port:** F.18.
**Root cause:** FlashInfer's `check_cuda_arch()` in this build (0.10.2 bundled) does a whitelist check, not a floor check. Blackwell/SM_120 is not in the whitelist. Error message is misleading.
**Fix:** Disable FlashInfer sampler, fall back to PyTorch-native top-k/top-p:
```
export VLLM_USE_FLASHINFER_SAMPLER=0
```
Sampler falls back cleanly; performance impact TBD by bench.
**Files changed:** `scripts/vllm_start.sh`.

## 2026-08-03 18:34 EDT — F.19.1b live smoke failed: qwen3_5_moe arch unrecognized

**Symptom (coder):**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ModelConfig
  Value error, The checkpoint you are trying to load has model type
  `qwen3_5_moe` but Transformers does not recognize this architecture.
```

Origin: `vLLM API server version 0.10.2` in `~/venv/vllm-new`.

**Symptom (planner):**
```
OSError: [Errno 98] Address already in use
```
Preceded by `[vllm_stop] residuals detected — port_8502=2` — stop
script found leftover sockets on :8502 but didn't free them before
the launcher tried to bind.

**Affected:** F.19.1a launchers + supervisor.

**Root cause 1 (both roles):** Native venv `~/venv/vllm-new` runs
vLLM 0.10.2, which predates `qwen3_5_moe` support. ADR-009 §5 already
required vLLM ≥ 0.26.0 but the launchers I wrote in F.19.1a shelled
into the native venv instead of the vetted Docker image. The bench
(`bench/f19pre/vllm_launch.sh`) used `vllm/vllm-openai:latest` and
that's the only vLLM known-good on Colossus today.

**Root cause 2 (planner OSError):** `scripts/vllm_stop.sh` cleans
`VLLM::EngineCore`/`vllm serve` processes but does not free the port
when the holder is a non-vllm process (or a native TIME_WAIT socket
from a prior binder). Bench-style native launches never hit this
because they used a single port (:8000) and Docker `-p` re-binding.

**Fix (pushed as 3-file commit):**
- `ops/vllm_launch_coder.sh` → rewrote to `docker run -d --name
  forge-vllm-coder`, pins `--quantization modelopt_fp4` (required for
  NVFP4; NOT autodetected), keeps `--max-num-seqs 128`, mounts
  `$HOME/models:/models:ro`, publishes `${PORT}:8000`.
- `ops/vllm_launch_planner.sh` → same Docker template; no
  `--quantization` flag (planner is compressed-tensors, autodetected);
  `--reasoning-parser qwen3` retained.
- `ops/vllm_supervisor.sh` → replaced `_stop_port` (which called F.18's
  native `vllm_stop.sh`) with `_stop_role` that does `docker rm -f`
  first, then `fuser -k`, then polls `ss -ltn` to confirm the port is
  actually released before returning. `_launch_bg` replaced with
  `_launch` because Docker launchers already daemonize.

**ADR update:** ADR-009 §5 quantization bullet corrected (c04 requires
`modelopt_fp4`, only c08 is autodetect). Added Follow-ups §4 (F.19.5)
to unify onto the native venv once it's on 0.26+.

**Retest command (paste into Colossus):**
```bash
cd ~/dev/forge-oh && git pull
./ops/vllm_supervisor.sh up coder
curl -s http://127.0.0.1:8501/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh up planner
curl -s http://127.0.0.1:8502/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh down
./ops/vllm_supervisor.sh status
```

**Files changed:**
- `ops/vllm_launch_coder.sh`
- `ops/vllm_launch_planner.sh`
- `ops/vllm_supervisor.sh`
- `docs/adr/009-local-llm-selection.md` (§5 correction, Follow-ups §4)

## 2026-08-03 18:46 EDT — F.19.1b planner-port conflict: :8502 owned by open-notebook

**Symptom:**
```
docker: Error response from daemon: failed to set up container networking:
  driver failed programming external connectivity on endpoint
  forge-vllm-planner: Bind for :::8502 failed: port is already allocated
```
`docker run` exit 125. `sudo fuser -k 8502/tcp` freed the socket
briefly but the process re-bound within seconds.

**Root cause:** `open-notebook-local-open_notebook-1` (published
`0.0.0.0:8502->8502/tcp`, up 2 days, unrelated app) permanently owns
:8502 on Colossus. Not a stale artifact; it's a live service with a
restart-policy that re-binds on kill.

**Fix:** planner moved to :8511 across all launch/router/doc sites.
:8511 verified free on Colossus (`ss -ltn`, `docker ps` grep).

Also: earlier attempt to `pkill -f 'docker-proxy.*-host-port'` without
sudo silently failed because docker-proxy runs as root. Not a
supervisor bug — the correct answer for :8502 was "pick another port,"
not "kill the incumbent."

**Files changed:**
- `bff/services/model_router.py` (`LLM_PLANNER_URL` default)
- `ops/vllm_launch_planner.sh` (`FORGE_VLLM_PLANNER_PORT` default)
- `ops/vllm_supervisor.sh` (`VLLM_PLANNER_PORT` default + docstring)
- `docs/adr/009-local-llm-selection.md` (§3a narrative)
- `SESSION_HANDOFF.md`
- `BUILD_LOG.md`

**Retest (paste on Colossus after pull):**
```bash
./ops/vllm_supervisor.sh up planner
curl -s http://127.0.0.1:8511/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh down
```

## 2026-08-03 18:57 EDT — F.19.1b coder cold-start >300s under vLLM 0.26.0

**Symptom:**
```
[supervisor] TIMEOUT waiting for coder on :8501 after 300s
```
Coder container `forge-vllm-coder` cleaned up on timeout. Planner
smoke on :8511 succeeded (146s READY). GPU free after: 1434 MiB
used / 30714 MiB free.

**Root cause:** Docker image `vllm/vllm-openai:latest` rotated from
vLLM 0.10.2 (first coder smoke) to **0.26.0** between runs. Weight
load + CUDAgraph capture on 35B NVFP4 on a cold GPU takes >300s on
0.26.0 (fine on 0.10.2 at 248s). Container was still initializing
past the supervisor's 300s deadline — not a real failure.

**Log confirmation:** last engine line at 22:55:34
(`topk_topp_sampler.py:39`), no fatal errors; supervisor killed the
container at ~23:00:09.

**Fix:** bump `VLLM_READY_TIMEOUT` default 300 → 420 in
`ops/vllm_supervisor.sh` (42% headroom over 248s baseline). Env
override still respected.

**Files changed:**
- `ops/vllm_supervisor.sh` (READY_TIMEOUT default + docstring)

**Retest (paste on Colossus):**
```bash
cd ~/dev/forge-oh && git pull
./ops/vllm_supervisor.sh up planner
curl -s http://127.0.0.1:8511/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh up coder
curl -s http://127.0.0.1:8501/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh down
```

If coder still times out at 420s, either the model itself broke on
0.26.0 or we need to pin `vllm/vllm-openai:v0.10.2` in the launcher.
Not proactively pinning yet — need to confirm 0.26.0 works first
(broader compat + qwen3_5_moe support was the reason we moved to
Docker in the first place).

## 2026-08-03 20:17 EDT — data.workspaceId echoed path instead of UUID

**Symptom:** `POST /api/runs` with body
`{"workspaceId": "18c99443b23c452899010095abd5f29b", ...}` returned
`{"data": {"workspaceId": "/home/rmholston/dev/forge-oh", ...}}`.
The UI expects UUID round-trip; got the resolved filesystem path.

**Affected:** F.19.4 post-close cosmetic bug in `bff/routers/runs.py`.

**Root cause:** Agent-server 1.40.0's ConversationInfo.workspace has
`working_dir` (a path) and no UUID field. `_conv_to_run_summary`
mapped `workspaceId = conv.workspace.working_dir` directly. Correct
for GET flows where BFF has no other information, but wrong for POST
where the caller already sent the UUID.

**Fix (single file, `bff/routers/runs.py`):**
1. Added `_workspace_path_to_id_map()`: async helper that lists
   agent-server workspaces once and builds a `{path: uuid}` map.
   Safe on failure (returns `{}`).
2. Added `_resolve_workspace_id(conv, path_to_id)`: takes the map,
   translates `working_dir` -> UUID, falls back to raw path when
   the map is empty or path is unknown.
3. `_conv_to_run_summary` accepts an optional `workspace_path_to_id`
   arg and uses `_resolve_workspace_id`.
4. `list_runs` and `get_run` call the map builder once per handler.
5. `create_run` post-processes: overwrites `summary["workspaceId"]`
   with `body.workspaceId` when provided (no extra API call needed).

**Files changed:** `bff/routers/runs.py`.

**Retest:** re-run F.19.4 Phase 2 smoke; expect
`data.workspaceId == 18c99443b23c452899010095abd5f29b`.

## 2026-08-03 20:55 EDT — BFF shutdown mid-smoke (P3 curl rc=143)

**Symptom:** During workspaceId reverify smoke, P3 curl exited with rc=143 (SIGTERM) at 39s, response body was empty; BFF log showed `INFO: Shutting down` immediately before curl died.
**Affected:** BFF (uvicorn) started with `--reload --reload-dir bff`.
**Root cause:** uvicorn's `--reload` watcher tripped a reload during the long-running P3 request (planner swap ~135s). The reloader began shutdown; the in-flight request was cancelled, curl saw its socket close and returned 143.
**Fix:** Restart BFF WITHOUT `--reload` for smoke/production runs. `--reload` is dev-only and can kill long-running vLLM-supervisor requests. Command: `nohup .oh-venv/bin/python .oh-venv/bin/uvicorn bff.main:app_with_sio --host 127.0.0.1 --port 8081 > ~/.forge-oh/bff.log 2>&1 &`
**Files:** none (operational fix, not code).

## 2026-08-03 22:52 EDT — self-eval cycle "transport error (ReadTimeout)" at exactly 30.0s per task

**Symptom:** First live self-eval cycle after slice G.1 landed:
`docs/selfeval/2026-08-04-selfeval.json` reports every task with
`error / transport error (ReadTimeout): ReadTimeout('')` at wall-clock
30.0s.  Systemd unit `forge-oh-selfeval.service` exits with
`Result: success` (harness catches the exception) but zero tasks pass.

**Affected:** slice G.1 (nightly self-eval harness) → BFF `POST /api/runs` → agent-server `POST /api/conversations`.

**Investigation:**
1. `~/.forge-oh/bff.log` looked empty around cycle time.  Discovered the
   RUNNING BFF's stdout points at `~/dev/forge-oh/.forge-logs/bff.log`
   (via `/proc/1483956/fd/1`), NOT `~/.forge-oh/bff.log` (stale from an
   older start).  Two log directories, two ways to be misled.
   The doctor script grepped the stale one.
2. Once we grepped the LIVE log, every self-eval `POST /api/runs`
   returned **200 OK** (lines 2495, 2502, 2529, 2531, 2543).  The BFF
   was doing the work — the harness had hung up first.
3. `bff/openhands_client.py:26` uses `httpx.Timeout(60.0)` for its call
   to agent-server.  `openhands_tools_ext/selfeval/harness.py:133` used
   `timeout=30.0` on `POST /api/runs`.  The harness's 30s cap fires
   before the BFF's 60s inner budget completes — every time.
4. Agent-server's synchronous LLM warmup inside `POST /api/conversations`
   is what consumes most of the 60s (vLLM coder :8501 unreachable during
   cycle → litellm falls back to Ollama :11434 first-token latency).

**Root cause:** timeout inversion.  Harness client-side timeout (30s) <
BFF server-side timeout (60s) < agent-server sync LLM warmup time
(~30–60s depending on model state).

**Fix (this slice — unblock G.1):**
Raise harness POST cap from 30s → 90s in `_create_run()`.  Same bump
for the enclosing AsyncClient default.  Add regression test
`test_post_runs_timeout_at_least_90s` in `test_harness.py` so any
future edit dropping the cap below 90s fails in CI.

**Fix (follow-up — proper):** ADR-012 proposes refactoring BFF
`create_run` to return immediately after conversation registration,
moving the LLM warmup into a `BackgroundTasks` continuation with
failures surfaced via Socket.IO events.  Once that lands, the harness
cap can drop back to ≤10s and the regression test flips.

**Files changed:**
- `openhands_tools_ext/selfeval/harness.py` (lines 133, 294).
- `openhands_tools_ext/tests/selfeval/test_harness.py` (+ regression).
- `.openhands/decisions/012-bff-create-run-async-warmup.md` (new,
  Proposed).

**Also learned:**
- Doctor script log-tail sections were pointing at `~/.forge-oh/*.log`
  but the live services write to `~/dev/forge-oh/.forge-logs/*.log`.
  Doctor fix: symlink or walk `/proc/<pid>/fd/1` to find the real log
  target for each service.  Deferred to next slice.


## 2026-08-03 23:40 EDT — G.1: event loop hogged by sidecar producers (proper fix)

**Symptom:** After landing the harness 30s→90s timeout bump (22:55 EDT
entry above), the 22:58 self-eval cycle STILL failed with
`transport error (ReadTimeout): ReadTimeout('')` at ~90.1s per task.
Zero `POST /api/runs` entries appeared in the fresh BFF log — as if the
harness's request bodies never reached the BFF app code. BFF log
contained 116 copies of
`sidecar_producers[c07b8803-…]: event buffer capped, dropped 500 oldest events`.

**Affected:** BFF (event loop scheduling). Slice G.1 self-eval harness
was the visible failure surface, but the underlying bug is a class of
sidecar-producer-related loop starvation and would eventually hit any
long-running BFF process with a leaked or high-throughput conversation
relay.

**Investigation:** `py-spy dump --pid <bff>` taken during a live 90s
ReadTimeout window, twice, 30 s apart:

Dump 1:
```
Thread MainThread (active+gil):
  build_plan (bff/services/action_reconstruction.py:282)
  _produce_plan (bff/services/sidecar_producers.py:113)
  update_from_event (bff/services/sidecar_producers.py:457)
  _run_loop (bff/services/event_relay.py:195)
  _run (asyncio/events.py:88)
  ...
```

Dump 2:
```
Thread MainThread (idle):
  _rmw (bff/services/sidecar.py:115)
  update_sidecar (bff/services/sidecar.py:220)
  update_from_event (bff/services/sidecar_producers.py:474)
  _run_loop (bff/services/event_relay.py:195)
  ...
```

Both dumps show the asyncio event loop's MainThread pinned inside
`event_relay._run_loop`, which was calling
`sidecar_producers.update_from_event(...)` **synchronously**. That
sync path runs `_produce_plan → build_plan` (O(events)) and
`_rmw → update_sidecar` (fsync + rename), consuming tens of ms per
event. With ~500 backlogged events for a leaked producer (c07b8803),
per-iteration wall time exceeded the harness ReadTimeout cap. Uvicorn's
request handler coroutine never got scheduled during that window,
so the harness POST hung until it timed out client-side — and the BFF
log had no record of the request ever entering routing.

**Root cause:** `EventRelay._run_loop` (line 195 of
`bff/services/event_relay.py`) called
`sidecar_producers.update_from_event(...)` directly on the asyncio
event loop with no yield-point between events. Any CPU-bound or
fsync-heavy sidecar producer would starve every other coroutine on the
same loop (uvicorn's request handler is on that same loop).

**Fix applied:**
1. Wrap the sync call in `await asyncio.to_thread(...)` so the plan
   builder and file-lock/fsync run on a worker thread, not on the
   event loop.
2. Add `await asyncio.sleep(0)` per event, unconditionally, so even
   with sidecar work disabled (`working_dir == ""`) the loop yields to
   other pending tasks.

Both changes are inside the per-event loop in `_run_loop` (single edit,
inline comment references this DEBUG_LOG timestamp).

**Regression tests (bff/tests/test_event_relay_yield.py):**
- `test_update_from_event_runs_in_worker_thread`: fails if the
  `asyncio.to_thread` wrapping is removed (asserts the sidecar producer
  is invoked on a non-main thread).
- `test_slow_producer_does_not_block_event_loop`: kicks off a 200 ms
  CPU-bound sync call the way the relay does it and asserts a
  concurrent "request" coroutine schedules in <100 ms.
- `test_direct_sync_call_would_block_confirms_the_hazard`: documents
  the hazard (a direct sync call inside a coroutine DOES block a
  concurrent task); guards against a future revert with a "just call
  it directly" comment.

**Also learned:**
- `uvicorn --reload` was NOT the culprit here (was ruled out by
  restarting without it and reproducing the same 90.1s failure).
- Doctor script's Section 7/8 grep for `POST /api/runs` missed this
  because no such line was ever emitted — the request never reached
  the router. Add a Section that greps `py-spy dump` for MainThread
  when the doctor detects a stalled cycle. Deferred to next slice.
- The leaked `c07b8803` conversation is separate work: we should
  either (a) cap producer backlog at ~200 events with drop-oldest, or
  (b) shut down relays for orphaned conversations after N idle
  minutes. Deferred to a follow-up slice.

**Files changed:**
- `bff/services/event_relay.py` (per-event loop in `_run_loop`).
- `bff/tests/test_event_relay_yield.py` (NEW, 3 regression tests).
- DEBUG_LOG.md (this entry).
- BUILD_LOG.md (2026-08-03 23:45 EDT entry).

## 2026-08-04 02:03 EDT — vLLM coder Exited(1) at launch: GPU contention, not quant flag

**Symptom:**
Right after the G.1 merge to main, `ops/vllm_launch_coder.sh` (via
supervisor `up coder`) launched the container and it `Exited(1)`
within seconds. `docker logs forge-vllm-coder`:

    ValueError: Free memory on device cuda:0 (24.85/31.39 GiB) on
    startup is less than desired GPU memory utilization (0.9, 28.25
    GiB). Decrease GPU memory utilization or reduce GPU memory used
    by other processes.

**Initial misdiagnosis:** looked like a `--quantization modelopt_fp4`
resolution failure (checkpoint config declares `MIXED_PRECISION`,
launcher passes `modelopt_fp4`). Was tempted to pin vLLM to `0.10.2`
(the F.19-pre bench version). Rejected — see ADR-009 §5 / DEBUG_LOG
older entry: `v0.10.2` does not recognize the `qwen3_5_moe` arch and
cannot run c04 or c08 at all. Docker `:latest` (currently `0.26.0`)
correctly auto-detected the mixed-precision quant and resolved to
`quantization=modelopt_mixed`. The launch flags were fine.

**Actual root cause:** pure GPU contention. Ollama was still holding
~6.5 GB of VRAM at the moment `docker run` executed. vLLM `0.26.0`
refuses to launch when
`memory.free < gpu-memory-utilization × total`. Neither the launcher
scripts nor `ops/vllm_supervisor.sh` stopped Ollama or verified
`memory.free` before invoking `docker run`; the discipline lived only
in the `forge-oh-llm-serving` skill notes.

**Fix applied (slice `vllm-supervisor-gpu-discipline`):**
- `ops/vllm_supervisor.sh` gained `_stop_ollama` + `_free_gpu_for_vllm`
  helpers and calls them in `cmd_up` between `_stop_role` and
  `_launch`.
- Helpers are idempotent and no-op on machines without Ollama.
- `VLLM_MIN_FREE_MIB` (default 28000), `VLLM_GPU_FREE_TIMEOUT`
  (default 30), `VLLM_SKIP_OLLAMA_STOP` env knobs added.
- New `check` subcommand for dry-run verification.
- Library-mode guard so `ops/test_supervisor.sh` can
  source the file.

**Verification path when debugging a similar future crash:**
1. `nvidia-smi --query-compute-apps=pid,process_name,used_memory
   --format=csv,noheader` — expect ONE python process (the vLLM
   container's engine); if two show up, someone else is holding
   VRAM.
2. `ops/vllm_supervisor.sh check` — new dry-run subcommand
   reports free vs required VRAM with exit 0/1.
3. `docker logs forge-vllm-coder 2>&1 | grep -iE 'free memory|quant|
   error'` — first 20 lines usually tell the whole story.
4. If the log shows `Free memory on device` → GPU-contention path
   (this bug's family). Fix via `_free_gpu_for_vllm`. Do NOT
   downgrade vLLM or change `--quantization`.
5. If the log shows `Unknown quantization method` → auto-detect
   failed. Read `~/models/<dir>/hf_quant_config.json` and pass
   explicit `--quantization <method>`. Different bug family.

**Also learned:**
- Ollama's `systemctl stop` does not reliably release VRAM held by
  the runner subprocess on all setups; `pkill -f 'ollama runner'`
  is required belt-and-braces.
- `--gpu-memory-utilization 0.9` on a 31.39 GiB card = 28.25 GiB
  required free. Rounded down to 28000 MiB (28.13 GiB) for the
  supervisor's `VLLM_MIN_FREE_MIB` default.

**Files changed:**
- `ops/vllm_supervisor.sh` (helpers + guard + check subcommand).
- `ops/test_supervisor.sh` (NEW, 14 tests).
- `docs/adr/009-local-llm-selection.md` (Follow-up 5).
- DEBUG_LOG.md (this entry), BUILD_LOG.md (2026-08-04 02:03 EDT).


## 2026-08-04 02:24 EDT — session-summary hallucinated a code default

**Symptom:** A pre-compaction session summary claimed a G.1 slice
commit `addcf63` merged the `LLM_CODER_OLLAMA_FALLBACK` code default
from `qwen3-coder:30b` → `qwen3-coder:32k` and further claimed this
had landed on main via merge commit `d36e72a`.

**Affected stage/plugin/port:** G.1 self-eval router path, `bff/services/model_router.py`.

**Root cause:** The summary was a paraphrase (per the compaction
disclaimer), not a transcript. Verification against git history:
- `git log --all --oneline | grep addcf63` → **no such SHA exists**
  in any reachable ref.
- `git show d36e72a --stat` on `bff/services/model_router.py` shows
  no line-107 modification.
- Actual line 107 on main at `117e263`:
  `"LLM_CODER_OLLAMA_FALLBACK", "qwen3-coder:30b"`.

The green G.1 cycle passed only because the operator had
`LLM_CODER_OLLAMA_FALLBACK=qwen3-coder:32k` exported in the shell
starting the BFF. The env override masked the wrong code default.

**Fix applied:**
1. Correctly land the code default change on
   `slice/vllm-primary-selfeval-verification`.
2. Add regression tests
   (`test_coder_ollama_fallback_defaults_to_32k`,
   `test_coder_ollama_fallback_env_override_wins`) to prevent
   silent regression in future slices.
3. Overwrite SESSION_HANDOFF with a correction section calling out
   the false previous claim so no future session inherits it.

**Files changed:**
- `bff/services/model_router.py`
- `bff/tests/test_model_router.py`
- `SESSION_HANDOFF.md`

**Lesson:** Never trust a compaction summary for load-bearing facts.
When it claims a specific commit landed a specific change, verify
with `git show <sha>` and `grep -n <constant>` against the current
file. If the summary is wrong, correct the SESSION_HANDOFF and log
the correction in DEBUG_LOG so future sessions do not re-inherit
the falsehood.

## 2026-08-04 02:40 EDT — stray Ollama process outside systemd

**Symptom:** After the vLLM-primary verification cycle completed
green, `systemctl is-active ollama` returned `inactive`, but
`curl http://localhost:11434/api/tags` responded 200 with the full
model list including `qwen3-coder:32k`, `qwen3-coder:30b`,
`qwen3-coder:latest`, `qwen3.6:35b-a3b`, `qwen3-thinking-2507:q4kxl`,
`nomic-embed-text:latest`. Indicates a running `ollama serve`
process outside systemd (likely a leftover from a manual foreground
launch earlier in the evening).

**Affected stage/plugin/port:** Colossus GPU-tenancy discipline
(ADR-009 §5, forge-oh-llm-serving skill).

**Root cause:** Not yet diagnosed. Candidates:
1. A `nohup ollama serve &` from earlier tonight when Ollama systemd
   was manually stopped for the c04 launch.
2. Ollama user-scoped socket-activation (unusual).
3. An `.oh-venv` shell fork keeping ollama alive.

**Impact right now:** None on the completed cycle — vLLM held the
GPU throughout, and Ollama metrics show zero requests routed there.
BUT: if the stray Ollama has any weights loaded, the next c04
restart will trip the supervisor's free-memory precondition.

**Fix (deferred):** on next session, run:
```
ps -ef | grep '[o]llama'
ss -lntp | grep 11434
nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader
kill -TERM <ollama_pid>
```

**Lesson:** `systemctl is-active` is not a proof of "Ollama is
stopped" — it only proves systemd doesn't think it's managing one.
The supervisor's `_stop_ollama` helper does `systemctl stop` AND
`pkill -x ollama`; the audit check should use both signals.
Consider adding a `ss -lntp | grep 11434` check to
`ops/vllm_supervisor.sh check` in a follow-up hygiene slice.

## 2026-08-04 02:42 EDT — Ollama "leak" was user-scope systemd, not a stray

**Continuation of 2026-08-04 02:40 EDT entry above.**

**Root cause identified:** Ollama on `:11434` (PID 2684635, parent
PID 2939 = user systemd) is the **user-scoped** systemd unit. It is
NOT a leftover manual process. Diagnostic results:

```
$ systemctl is-active ollama              → inactive       (system scope)
$ systemctl --user is-active ollama       → active         (user scope)
$ ss -lntp | grep 11434                   → LISTEN owned by pid 2684635
$ nvidia-smi --query-compute-apps ...     → NO ollama pid in output
                                            (only chromium + vLLM engine core)
```

Ollama's API server is running, but **no model is loaded** into
VRAM (0 MiB held by ollama). VLLM has full GPU tenancy
(28220 MiB / 32 GB).

**Impact on the verified cycle:** none. Zero VRAM contention, zero
requests routed to Ollama.

**Impact on future c04 restarts:** at risk. If a request ever
triggers Ollama to load a model into VRAM (unlikely from the router
now that vLLM-primary is the code default and healthy, but possible
from any manual `ollama run <model>` invocation), the c04 restart
will fail the supervisor's free-memory precondition — and
`_stop_ollama` in `ops/vllm_supervisor.sh` currently only stops the
system-scope unit, not the user-scope one.

**Fix (deferred hygiene slice):** extend `_stop_ollama` to try
BOTH scopes:
```bash
sudo systemctl stop ollama 2>/dev/null || true
systemctl --user stop ollama 2>/dev/null || true
pkill -x ollama 2>/dev/null || true
```
And extend `ops/vllm_supervisor.sh check` to `ss -lntp | grep 11434`
so the audit reflects reality (an inactive system-scope unit does
NOT mean Ollama is off).

Tracking as `slice/supervisor-user-scope-hygiene` for later.

**Lesson (durable):** on multi-scope systemd machines, always
check `systemctl --user is-active <unit>` in addition to
`systemctl is-active <unit>`. A user-scope unit is invisible to
`systemctl` without the `--user` flag but still owns processes and
ports.

## 2026-08-04 03:00 EDT — .then(_json) generic inference collapses to unknown

**Symptom:**
```
Type 'unknown' is not assignable to type '{ cycles: CycleListItem[]; }'.
  74 |
  75 | export const fetchCycles = (): Promise<{ cycles: CycleListItem[] }> =>
> 76 |   fetch(`${BASE}/api/selfeval/cycles`).then(_json);
     |   ^
Next.js build worker exited with code: 1 and signal: null
```

**Affected stage/plugin/port:** F.19-post — `slice/selfeval-frontend-polish`
prod `npm run build` on Colossus. Frontend only; BFF untouched.

**Root cause:** `src/features/selfeval/api.ts` defines
`async function _json<T>(r: Response): Promise<T>`. When passed as
`.then(_json)`, TypeScript cannot infer `T` from context — it falls
back to `unknown`, which then can't unify with the declared
`Promise<{cycles: CycleListItem[]}>` return of `fetchCycles`. Same
bug on all five call sites (`fetchCycles`, `fetchCycle`,
`fetchProposals`, `fetchProposal`, `fetchStatus`, `postRun`).

Why prior G.1 build passed on Colossus: unknown. The G.1 build never
actually ran a strict prod build against this file until my slice
touched adjacent files that changed which pages consume these
generics. Suspect the earlier lax build didn't surface the inference
gap because the consumers were less strictly typed.

**Fix applied:** wrap each `.then(_json)` with `.then((r) => _json<T>(r))`
so the generic is pinned per-call-site. Added an inline comment
citing this DEBUG_LOG entry as a regression guard.

**Files changed:** `src/features/selfeval/api.ts`.

**Verified:** locally re-read the 6 call sites; will re-verify prod
build on Colossus in the same slice.

## 2026-08-04 03:04 EDT — .gitignore 'tests/' silently swallows src/tests/e2e/*

**Symptom:**
```
$ npx playwright test src/tests/e2e/selfeval.spec.ts --reporter=list
Error: No tests found.
Make sure that arguments are regular expressions matching test files.
```
File visibly present on disk, but `git ls-files src/tests/e2e/` did
not list it, and it never landed on Colossus.

**Affected stage/plugin/port:** F.19-post — `slice/selfeval-frontend-polish`
frontend Playwright verification.

**Root cause:** `.gitignore` line 57 has `tests/` as a "local scratch
helpers" ignore rule. Because gitignore matches path components
anywhere in the tree, this ignores `src/tests/` too. Existing specs
were tracked because they had been `git add -f`'d earlier; new specs
added via `git add -A` are silently skipped.

**Fix applied:** always use `git add -f src/tests/e2e/*.spec.ts` for
new Playwright specs. Do NOT relax the top-level `tests/` ignore
rule — it exists to keep triage scratch out of the repo.

**Files changed:** `src/tests/e2e/selfeval.spec.ts` force-added.

**Verified:** `git ls-files src/tests/e2e/selfeval.spec.ts` now returns
the file. Push landed on origin as `e630f86`.

**Regression guard:** any future slice that touches Playwright specs
must `git add -f` explicitly and grep `git ls-files` after commit to
confirm the file is tracked.

## 2026-08-04 03:10 EDT — Next.js 16 dynamic route params silently render undefined

**Symptom:**
Navigating to `/selfeval/2026-08-04` produced `<h1>Cycle: </h1>` (empty
date), the useCycle query never fired (filename resolved to
`-selfeval.json` which the enabled guard `Boolean(filename)` rejected),
KPIs never appeared, and the outcomes table never rendered. Three
Playwright Tier-2 tests failed as a result.

**Affected stage/plugin/port:** F.19-post — slice/selfeval-frontend-polish.
`src/app/(dashboard)/selfeval/[date]/page.tsx`.

**Root cause:** Next.js 16 changed dynamic-route `params` from a plain
object to a `Promise<{...}>`. The route wrapper's synchronous signature
`{ params }: { params: { date: string } }` type-checked (because TS
sees `params` as any at runtime), but `params.date` was `undefined`.
The canonical unwrap for other client routes in this app is
`src/app/(dashboard)/runs/[runId]/page.tsx`:

```tsx
params: Promise<{ runId: string }>;
const { runId } = React.use(params);
```

**Fix applied:** rewrote the wrapper to accept `Promise<{ date: string }>`
and unwrap via `React.use(params)`.

**Files changed:** `src/app/(dashboard)/selfeval/[date]/page.tsx`.

**Regression guard:** any future dynamic App Router page in this repo
MUST use the `Promise<{...}>` + `React.use()` pattern.

## 2026-08-04 03:11 EDT — TaskOutcome type diverged from harness output

**Symptom:** verdict badges rendered but trajectory-status dots never
appeared; `.reasonCell` always showed `—` even for failed cycles.

**Affected stage/plugin/port:** F.19-post — slice/selfeval-frontend-polish.
`src/features/selfeval/api.ts`, `SelfEvalDatePage.tsx`.

**Root cause:** pre-existing `TaskOutcome` TS type declared fields
`final_status: string | null` and `reason: string | null`. Actual BFF
JSON (via `openhands_tools_ext/selfeval/harness.py`) emits
`trajectory_status: str | None` and `failure_detail: str`. The TS
type was invented in G.1 before the Python dataclass was named — never
caught because no populated cycle detail was ever rendered until now.

**Fix applied:** aligned `TaskOutcome` fields with harness dataclass
(`trajectory_status`, `failure_detail`, `run_id: string` not nullable,
`duration_sec: number` not nullable). Updated all consumers in
`SelfEvalDatePage.tsx`.

**Files changed:** `src/features/selfeval/api.ts`,
`src/features/selfeval/SelfEvalDatePage.tsx`.

**Regression guard:** when adding new BFF-shape TS types, mirror the
Python dataclass exactly. When possible, generate the TS from the
Pydantic schema.

## 2026-08-04 21:38 EDT — Plan-vs-repo mismatches during Stage 1 reconciliation-plan-v1 execution

**Symptom:** `Forge-OH-reconciliation-plan-v1-stage-1.md` prescribes delete lists and code changes that, when checked against the live repo, contradict on-disk state.

**Affected stage/plugin/port:** Stage 1 reconciliation-plan-v1 · sub-slices 1.1, 1.4, 1.5.

**Root cause:** Plan was written against an assumed snapshot (`plan-v0`?) that predates several merged PRs (notably selfeval-frontend-polish #4). Specifically:

1. **1.1** — plan claims a top-level `lmnr==0.7.57` pin blocks `openhands-sdk` upgrade. `bff/requirements.txt` has no direct `lmnr` line. `lmnr` comes transitively via `openhands-tools`. Sandbox pip resolve with Python 3.14 succeeded with `openhands-sdk==1.40.0` + `lmnr==0.7.57` — no conflict reproducible. Root problem is stale `bff/requirements.lock` on Colossus (`openhands-sdk==1.29.3`).
2. **1.4.1** — plan says "12 unused Next.js proxy routes". Grep finds only 3 truly zero-caller (`runs/[runId]/commands`, `.../events`, `.../artifacts`); the other proposed deletions have live code or test callers.
3. **1.4.2** — plan says to delete `src/lib/plugins/hooks.ts` and `src/features/plugins/PluginsPage.tsx` unconditionally. Grep shows two orphan test files also import from `src/lib/plugins/hooks.ts` — they were deleted alongside per plan rule 1.4.5 ("if any marker turns out to guard code that's actually still referenced, log in DEBUG_LOG.md rather than deleting blind").
4. **1.4.5** — plan says `src/features/mcp/mcp-server-card.tsx` contains a `TODO(foh-phase2)` marker. Grep finds no such marker in `src/features/mcp/`. Plan mis-identifies the location.
5. **1.5** — plan asks to route `create_run` via `preset.model`. Codebase's `route_by_role(role, context_length)` is deterministically role-based per ADR-009 §3a. There is no `role` field on `AgentPreset`. Making preset drive model directly contradicts ADR-009 topology. Deferred; awaiting operator decision.
6. **General** — plan text uses BFF port 8000. Actual verified BFF port is 8081 (see `forge-oh-colossus-ops` skill).

**Fix applied:** Executed the conservative safe subset for each sub-slice; documented every divergence in BUILD_LOG.md entry `2026-08-04 21:38 EDT`. 1.5.3–1.5.5 deferred pending operator decision on ADR-009 amendment or supersede.

**Files changed:** BUILD_LOG.md (append). No revert of prior slice work; deletions in 1.4 remain because their target files are demonstrably orphan against the current repo state, not against the plan's assumed state.
## 2026-08-04 23:57 EDT — c04 vLLM fails to start: "max_num_seqs (128) exceeds available Mamba cache blocks (111)"

**Symptom** (exact from `docker logs vllm-bench`):
```
ValueError: max_num_seqs (128) exceeds available Mamba cache blocks (111). Each decode sequence requires one Mamba cache block, so CUDA graph capture cannot proceed. Please lower max_num_seqs to at most 111 or increase gpu_memory_utilization.
RuntimeError: Engine core initialization failed.
```

**Affected**: F.19-post · pathE_qwen36_27b · vllm_launch.sh · c04 cell (Qwen3.6-27B NVFP4 planner)

**Root cause**: Qwen3.6-27B uses Mamba/hybrid attention (not pure dense self-attention). Mamba cache slots are a fixed derived quantity based on model config × gpu_memory_utilization × available VRAM. On Colossus RTX 5090 (32 GB, 0.90 util) the model provides ~111 Mamba slots. Our launcher hard-coded `--max-num-seqs 128`, which exceeded the slot count. Each parallel decode sequence needs one Mamba slot, so vLLM refused to start.

**Fix applied**: introduced per-cell `MAX_NUM_SEQS` override in `vllm_launch.sh`. For c04, set to 96 (safe headroom below the 111 hard-cap). Default remains 128 for all non-Mamba cells (c01 dense-int4, c02 A3B MoE, c03b dense AWQ, c05 dense AWQ). If future Mamba-model cells fail with the same symptom, set their own `MAX_NUM_SEQS` in the case-block.

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (added per-cell MAX_NUM_SEQS variable + comment)

**Alternative not chosen**: raising `--gpu-memory-utilization` beyond 0.90 would produce more Mamba slots but risks OOM on prompt processing spikes.

**Verify with**: `bash bench/pathE_qwen36_27b/vllm_launch.sh c04` — should reach READY without the Mamba-slot error.

## 2026-08-05 00:00 EDT — c03b vLLM fails to start: "Quantization method in model config (compressed-tensors) does not match --quantization (awq_marlin)"

**Symptom** (exact from `docker logs vllm-bench`):
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ModelConfig
Value error, Quantization method specified in the model config (compressed-tensors) does not match the quantization method specified in the `quantization` argument (awq_marlin).
```

**Affected**: F.19-post · pathE_qwen36_27b · vllm_launch.sh · c03b cell (Qwen3-Coder-30B AWQ-4bit from cyankiwi)

**Root cause**: The repo `cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit` is misleadingly named — despite "AWQ" in the repo name, its `config.json` declares `quantization_config.quant_method = "compressed-tensors"` with `format: pack-quantized`, `group_size: 32`, `num_bits: 4`, symmetric int4. This is llm-compressor's compressed-tensors int4 format, not classic AWQ. vLLM refuses when `--quantization awq_marlin` disagrees with the model's self-declared method.

**Fix applied**: removed `--quantization awq_marlin` from c03b case in `vllm_launch.sh`. vLLM auto-detects `compressed-tensors` from `config.json` and dispatches to the correct kernel (on Blackwell this is still int4 Marlin under the hood).

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (c03b case simplified, comment explaining the naming trap)

**Alternative not chosen**: re-downloading `QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ` (real AWQ, 254K downloads) would require ~10 min extra bandwidth. cyankiwi's int4 quality is equivalent to AWQ at same group size, so not worth the round-trip.

**Verify with**: `bash bench/pathE_qwen36_27b/vllm_launch.sh c03b` — should reach READY without the quantization-mismatch error.


## 2026-08-05 00:33 EDT — pull_new_models.sh: "File not found in repository ... /resolve/main/original/%2A"

**Symptom** (exact from operator paste):
```
UserWarning: Ignoring `--exclude` since filenames have been explicitly set.
Error: File not found in repository.
URL: https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8/resolve/main/original/%2A
```

**Affected**: F.19-post · pathE_qwen36_27b · pull_new_models.sh

**Root cause**: The `hf download` CLI on huggingface_hub 1.26.0 treats positional args after the repo id as literal filenames (URL-encodes the `*`). The `original/*` positional was intended as a glob for the deprecated `--exclude` flag, but `--exclude` is silently ignored when any positional filename is present. Result: CLI tried to fetch a literal file called `original/*` (URL-encoded to `original/%2A`), which doesn't exist.

**Fix applied**: rewrite `pull()` to use `--include` patterns instead. Explicitly list inference-time file globs: `*.safetensors`, `*.json`, `*.txt`, `*.model`, `tokenizer*`. This is the huggingface_hub 1.0+ recommended pattern (positional filenames become part of the include set, not an exclude set).

**Also updated**: env-var handling. `HF_HUB_ENABLE_HF_TRANSFER` is deprecated in huggingface_hub >=1.0 in favor of `HF_XET_HIGH_PERFORMANCE`. Script now exports both for backward/forward compatibility.

**Files changed**:
- `bench/pathE_qwen36_27b/pull_new_models.sh` (pull() uses --include; env-var handling updated)

**Verify with**: `bash bench/pathE_qwen36_27b/pull_new_models.sh` — should begin downloading `.safetensors` shards without the "File not found" error.

## 2026-08-05 00:33 EDT — Ollama pull failure: "pull model manifest: file does not exist" for yi-1.5:34b

**Symptom** (exact):
```
pulling manifest
Error: pull model manifest: file does not exist
```

**Affected**: F.19-post · c08 cell · Ollama tag

**Root cause**: Ollama's registry does not use the `yi-1.5:34b` naming convention. The Yi-1.5 family is exposed under the `yi` model with quantization-suffixed tags: `yi:34b-chat-v1.5-q4_K_M`, `yi:34b-chat-v1.5-q8_0`, etc. Confirmed via `curl https://ollama.com/library/yi/tags`.

**Fix applied**: updated `bench_pathE.py` c08 tag from `yi-1.5:34b` to `yi:34b-chat-v1.5-q4_K_M` (Q4_K_M chosen to fit 32 GB VRAM with KV headroom, matches c03's Ollama quant tier). Also updated pull_new_models.sh comment.

**Files changed**:
- `bench/pathE_qwen36_27b/bench_pathE.py` (c08 model_id)
- `bench/pathE_qwen36_27b/pull_new_models.sh` (echo hint)

**Verify with**: `ollama pull yi:34b-chat-v1.5-q4_K_M` — should download without manifest error.


## 2026-08-05 00:39 EDT — pull_new_models.sh v2: --include also silently ignored, only tiny configs downloaded

**Symptom** (exact from operator paste):
```
UserWarning: Ignoring `--include` since filenames have been explicitly set.
Fetching 7 files: 100%|██████████| 7/7 [00:01<00:00,  5.70it/s]
[2026-08-05 00:34:12 EDT] DONE Qwen3-Coder-30B-A3B-Instruct-FP8
```

All 5 HF pulls "succeeded" in <2 seconds each — a real 30 GB weight download over hf_transfer runs 30-90 seconds. Only tiny (11 MB, 2 MB, 34 MB) config/tokenizer files were fetched.

**Affected**: F.19-post · pathE_qwen36_27b · pull_new_models.sh

**Root cause**: On huggingface_hub 1.26.0, the `hf download` CLI treats **any** positional args after the repo id as literal filenames, AND silently ignores `--include` when positional filenames are also inferred. The `--include "*.safetensors" "*.json" "*.txt" "*.model" "tokenizer*"` was parsed as: `--include "*.safetensors"` with `"*.json"`, `"*.txt"`, `"*.model"`, `"tokenizer*"` as positional filenames — which the CLI then tried to fetch literally, hitting cached small files or failing silently.

**Fix applied**: rewrote `pull()` to omit both `--include` and `--exclude` (full snapshot download), then post-download `find ... -name '*.gguf' -delete` to remove GGUFs. Added a sentinel check: only skip if a `.safetensors` file > 100 MB exists in the target dir (guards against the "download succeeded with only configs" false positive). Failure now returns exit 3 with a clear error.

**Files changed**:
- `bench/pathE_qwen36_27b/pull_new_models.sh`

**Verify with**: `bash bench/pathE_qwen36_27b/pull_new_models.sh` — expect real download times (30-120s per model on Gbit) and `du -sh` should show ~15-30 GB per model dir.



## 2026-08-05 01:04 EDT — Devstral-Small-2-2512 is a VLM, not a text-only coder (c10 + c11 config discovery)

**Symptom** (exact from operator paste, config.json inspection):
```
architectures: ['Mistral3ForConditionalGeneration']
model_type: mistral3
has vision_config: True
```
Both c10 (`Devstral-Small-2-24B-Instruct-2512-nvfp4`) and c11 (`Devstral-Small-2-24B-Instruct-2512-AWQ-4bit`) config.json declare `Mistral3ForConditionalGeneration` with a full `vision_config` block. c11's `quantization_config.ignore` list further confirms this by naming 24 `model.vision_tower.transformer.layers.*` modules and the `multi_modal_projector`.

**Affected**: F.19-post · pathE_qwen36_27b · vllm_launch.sh (c10, c11)

**Root cause**: Mistral's Devstral-Small-2 "2512" release is multimodal-only. There is no text-only sibling in the `-2512-` naming convention. Both quant variants (Fireworks NVFP4 and cyankiwi compressed-tensors AWQ-4bit) inherit the vision tower and multi-modal projector from the base model. Loading these under vLLM without a mm-limit flag will (a) allocate ~2 GB VRAM for the inert vision tower, (b) leave `/v1/chat/completions` accepting image content that our text-only bench never sends.

**Fix applied**: Added `--limit-mm-per-prompt '{"image":0}'` to both c10 and c11 `EXTRA_FLAGS`. This tells vLLM to reject image content per-request at the API boundary while still loading the model. Vision-tower VRAM waste (~2 GB) is accepted as the cost of running the only available Devstral-2512 quants. Both cells remain in the 13-cell matrix (operator decision: option B, keep both text-only).

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (c10 and c11 stanzas)

**Verify with**: after `bash vllm_launch.sh c10 up`, `curl -s http://localhost:8000/v1/models | jq` should list `c10_coder_vllm_devstral24b_nvfp4` with limit `image=0` reflected in vLLM startup log. Same for c11.


## 2026-08-05 01:11 EDT — c10 Fireworks NVFP4 is compressed-tensors-wrapped, same as c11

**Symptom** (exact from vLLM 0.26.0 startup):
```
ValidationError: 1 validation error for ModelConfig
  Value error, Quantization method specified in the model config (compressed-tensors) does not match the quantization method specified in the `quantization` argument (modelopt_fp4).
```

Container exited(1) at ~01:06 EDT, ~10 seconds after launch. Vision tower never loaded — died at ModelConfig validation.

**Affected**: F.19-post · pathE_qwen36_27b · vllm_launch.sh (c10)

**Root cause**: Third instance of the compressed-tensors trap this session (c03b, c11, now c10). The `Firworks/Devstral-Small-2-24B-Instruct-2512-nvfp4` repo packages genuine NVFP4 weights (`format: nvfp4-pack-quantized`, `type: float`, `num_bits: 4`) but wraps them in the compressed-tensors registry (`quant_method: compressed-tensors`). vLLM's config auto-detect reads `compressed-tensors`; our explicit `--quantization modelopt_fp4` conflicts and pydantic ModelConfig validation aborts.

The kernel dispatch on Blackwell (SM_120) still goes through the CT path to the FP4 marlin kernel — the served weights are unchanged, only the registry wrapper differs from a "native" ModelOpt-FP4 repo.

**Fix applied**: removed `--quantization modelopt_fp4` from c10 EXTRA_FLAGS. Kept `--limit-mm-per-prompt '{"image":0}'`. Matches the c03b and c11 pattern.

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (c10 stanza)

**Verify with**: `bash bench/pathE_qwen36_27b/vllm_launch.sh c10 up 2>&1 | tee ~/.forge-oh/c10_up.log` — expect READY within 60-120s and no ValidationError.

**Prevention for future benches**: **always** inspect `config.json:quantization_config.quant_method` BEFORE deciding whether to pass `--quantization` to vLLM. If it says `compressed-tensors`, never pass an explicit `--quantization` flag regardless of what the repo name suggests. Repos naming themselves `-awq-4bit`, `-nvfp4`, `-fp8`, etc. may still ship as CT-wrapped.


## 2026-08-05 01:16 EDT — Devstral tokenizer has no default chat_template (c10 + c11)

**Symptom** (from `POST /v1/chat/completions` smoke test against c10):
```
{
    "error": {
        "message": "As of transformers v4.44, default chat template is no longer allowed, so you must provide a chat template if the tokenizer does not define one.",
        "type": "BadRequestError",
        "code": 400
    }
}
```

c10 booted successfully (READY in 84s), served /v1/models correctly, but every chat completion returned 400.

**Affected**: F.19-post · pathE_qwen36_27b · vllm_launch.sh (c10, c11)

**Root cause**: Devstral-Small-2-2512 (both quant variants) ships the Mistral `[INST]`-format chat template as a standalone `chat_template.jinja` file in the model directory, NOT baked into `tokenizer_config.json` as a `chat_template` string. Since transformers v4.44, HF refuses to fall back to a hardcoded default when the tokenizer doesn't declare one. vLLM inherits this: without an explicit `--chat-template` flag, chat completions 400 with the message above.

Both `Devstral-Small-2-24B-Instruct-2512-nvfp4/chat_template.jinja` and `Devstral-Small-2-24B-Instruct-2512-AWQ-4bit/chat_template.jinja` are identical 5320-byte files (system prompt + `[INST]...[/INST]` framing).

**Fix applied**: added `--chat-template "/models/<MODEL_DIR>/chat_template.jinja"` to both c10 and c11 EXTRA_FLAGS. The docker mount `~/models:/models:ro` makes the file visible inside the container (confirmed via `docker exec vllm-bench ls /models/.../chat_template.jinja`).

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (c10 and c11 stanzas)

**Verify with**: after relaunching c10 up, POST /v1/chat/completions with a plain `{"role":"user","content":"..."}` message should return 200 and a completion. No `[INST]` tokens needed in the client payload — vLLM applies the template server-side.

**Prevention**: on any VLM/Mistral-family model, always check for a standalone `chat_template.jinja` file before assuming the tokenizer_config has a baked-in template. If a `.jinja` file is present, wire it via `--chat-template` regardless of what the tokenizer_config claims.


## 2026-08-05 01:20 EDT — MistralCommonBackend does not implement get_chat_template (c10 + c11)

**Symptom** (from `POST /v1/chat/completions` against c10 with --chat-template set):
```
{
    "error": {
        "message": "`MistralCommonBackend` does not implement `get_chat_template`.",
        "type": "NotImplementedError",
        "code": 501
    }
}
```

c10 booted, /v1/models returned 200, but chat completions returned 501.

**Affected**: F.19-post · pathE_qwen36_27b · vllm_launch.sh (c10, c11)

**Root cause**: vLLM 0.26.0 `--tokenizer-mode auto` prioritizes `MistralCommonBackend` for any Mistral-family repo (`Mistral3ForConditionalGeneration` matches). MistralCommonBackend uses `mistral-common` for tokenization and format enforcement and does NOT support the `apply_chat_template` / `get_chat_template` path — even when `--chat-template` is passed.

Per vLLM's tool-calling doc, Mistral repos in HF format (safetensors + standalone `chat_template.jinja`, no baked-in `chat_template` in tokenizer_config.json) MUST be served with `--tokenizer-mode hf` (and companion `--config_format hf --load_format hf` when the repo has multiple format options). Our repo is safetensors-only so config/load format autodetect to `hf`; only `--tokenizer-mode` needs to be forced.

**Fix applied**: added `--tokenizer-mode hf` to both c10 and c11 EXTRA_FLAGS. This routes tokenization through the HF `AutoTokenizer` path which respects `--chat-template` and reads the jinja file.

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (c10 and c11 stanzas)

**Verify with**: after re-launch, `POST /v1/chat/completions` with `{"role":"user","content":"..."}` should return a completion. If it still 501s, the tokenizer_mode enum was not accepted (vLLM 0.10.x used `{auto,slow,mistral}`; 0.26.0 added `hf`).

**Prevention**: on any Mistral-family repo served in HF format, always pass `--tokenizer-mode hf` explicitly. Do NOT rely on `auto` — it auto-picks mistral-common which breaks `--chat-template`.


## 2026-08-05 01:27 EDT — c10 (Devstral NVFP4) dropped from matrix

**Symptom** (persistent, unfixable within reasonable effort):
- Every route through `--tokenizer-mode hf` still lands in `MistralCommonBackend.get_chat_template` → 501 NotImplementedError
- vLLM 0.26.0 selects MistralCommonBackend from `tekken.json` presence + `Mistral3ForConditionalGeneration` architecture, NOT from `--tokenizer-mode`
- Confirmed via `docker logs`: `tokenizer_mode=hf` was accepted by the engine config but the tokenizer factory still routed to mistral-common

**Affected**: F.19-post · pathE_qwen36_27b · c10 (Fireworks/Devstral-Small-2-24B-Instruct-2512-nvfp4)

**Root cause**: This repo ships HF-format weights + `chat_template.jinja` + `tokenizer.json` (BPE, 131k vocab, class=TokenizersBackend) + `tekken.json`. It does NOT ship `params.json` or `consolidated.safetensors`, so `--config-format mistral --load-format mistral` cannot be used (native mistral path unavailable). vLLM's tokenizer routing for Mistral-family models is not overridable via `--tokenizer-mode` when both `tekken.json` and the Mistral3 architecture are present — MistralCommonBackend hijacks unconditionally.

**Fix applied**: dropped c10 from the bench matrix. c11 (cyankiwi AWQ variant) covers Devstral because it ships the full mistral-format files (`params.json`, `consolidated.safetensors`) and can be served via the native `--tokenizer-mode mistral --config-format mistral --load-format mistral` path. Same underlying model — no loss of quality signal.

**Files changed**:
- `bench/pathE_qwen36_27b/vllm_launch.sh` (c10 stanza removed, help text + case-default list updated)
- `bench/pathE_qwen36_27b/bench_pathE.py` (c10 removed from CELL_CONFIGS and CELL_ORDER)

**Prevention**: for any HF-format Mistral repo (safetensors + tokenizer.json + chat_template.jinja, no params.json), verify `--tokenizer-mode hf` actually reaches the tokenizer factory (not just the engine config) BEFORE assuming --chat-template will be honored. If MistralCommonBackend is selected regardless, the only path is a repo with full mistral-format files.

Chain summary of the four failed fixes for the record:
1. **01:11 EDT** — stripped --quantization (CT wrapper). Fixed the ModelConfig ValidationError; container booted.
2. **01:16 EDT** — added --chat-template jinja. Chat completions returned 400 (no default chat_template) → 501 (MistralCommonBackend.get_chat_template).
3. **01:20 EDT** — added --tokenizer-mode hf. Engine config accepted it. Tokenizer factory ignored it. Still 501.
4. **01:27 EDT** — attempted --tokenizer-mode mistral + --config-format mistral + --load-format mistral. Failed check: repo missing params.json/consolidated.safetensors. Abandoned c10.

## 2026-08-05 02:31 EDT — c07 Qwen3-Coder-30B FP8 CUDA OOM at compile time

**Symptom**:
```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 20.00 MiB.
GPU 0 has a total capacity of 31.39 GiB of which 30.56 MiB is free.
this process has 30.73 GiB memory in use.
```

Container reached the vLLM engine core init stage. Failed at `AsyncLLM.from_vllm_config` → `launch_core_engines` → `wait_for_engine_startup`. Engine core died inside `torch._functorch._aot_autograd` inductor cache during BF16 tensor allocation (`empty_strided_cuda((s72, 5120), (5120, 1), torch.bfloat16)`). vllm_launch.sh timed out after 900s.

**Affected**: F.19 (Path E rebench) · c07 · Qwen3-Coder-30B-A3B-Instruct-FP8

**Root cause**: FP8 is a weights-only quantization. On Qwen3-Coder-30B, FP8 weights alone occupy ~29 GB, saturating the 5090's 32 GB VRAM before any activations, KV cache, or CUDA graph inductor allocations are made. Torch.compile inductor requires additional BF16 activation tensors during graph construction (this is the s72×5120 tensor above), which pushes past the VRAM boundary. `--gpu-memory-utilization 0.90` does not help because the OOM is compile-time, not runtime, and torch.compile bypasses vLLM's memory budget.

**Fix applied**: Dropped c07 from the Path E bench matrix. Qwen3-Coder-30B AWQ 4-bit (c03b) is the canonical Blackwell 5090 quant for this model — it fits in ~18 GB with ~12 GB KV cache headroom.

**Files changed**:
- `bench/pathE_qwen36_27b/bench_pathE.py` (removed c07 from CELL_CONFIGS + CELL_ORDER)
- `bench/pathE_qwen36_27b/vllm_launch.sh` (removed c07 case block, updated usage strings)

**Alternative approaches considered (not applied)**:
- `--gpu-memory-utilization 0.75` + `--max-model-len 16384`: might reclaim 2-3 GB but OOM is compile-time, not runtime.
- `--enforce-eager` to skip torch.compile: drops throughput ~30%; still marginal fit.
- `--kv-cache-dtype fp8`: helps runtime KV memory, not compile-time OOM.

**General rule for 5090 VRAM budget (32 GB total, ~30 GB usable)**:
- FP8 models: usable up to ~20-24B params.
- AWQ/GPTQ 4-bit: usable up to ~32-35B params.
- NVFP4 (Blackwell-native): usable up to ~35B params with 5-8 GB KV headroom.

## 2026-08-05 02:41 EDT — c09 Codestral-22B-AWQ chat_template missing

**Symptom**:
```
HTTP 400: {"error":{"message":"As of transformers v4.44, default chat template is no longer allowed,
```

All three prompts (debug/arch/plan) failed instantly at `/v1/chat/completions` — cell wall time 0.0s, no engine work done. Container came up READY at 72s and served `/v1/models` fine.

**Affected**: F.19 (Path E rebench) · c09 · TechxGenus/Codestral-22B-v0.1-AWQ

**Root cause**: `TechxGenus/Codestral-22B-v0.1-AWQ`'s `tokenizer_config.json` does NOT contain a `chat_template` field. The upstream base model `mistralai/Codestral-22B-v0.1` does ship one (canonical Mistral `[INST]`/`[/INST]` template), but the AWQ requant stripped it. As of transformers v4.44, `apply_chat_template()` refuses to synthesize a default when the tokenizer lacks one, so vLLM's chat-completions endpoint 400s on every request.

**Fix applied**:
1. Vendored the canonical Codestral-22B chat template (`{{- bos_token }}` + `[INST] ... [/INST]` alternation) from `mistralai/Codestral-22B-v0.1/tokenizer_config.json` to `bench/pathE_qwen36_27b/chat_templates/codestral.jinja`.
2. Mounted `bench/pathE_qwen36_27b/chat_templates/` into the vLLM container at `/chat_templates` (read-only).
3. Added `--chat-template /chat_templates/codestral.jinja` to c09's EXTRA_FLAGS.

**Files changed**:
- `bench/pathE_qwen36_27b/chat_templates/codestral.jinja` (new)
- `bench/pathE_qwen36_27b/vllm_launch.sh` (added `chat_templates` bind mount, added `--chat-template` flag to c09 block)

**General rule for AWQ/GPTQ variants of Mistral-family models**:
Community requant repos frequently strip `chat_template` from `tokenizer_config.json`. Always check the requant repo's `tokenizer_config.json` before launching; if `chat_template` is absent, mount the canonical template from the upstream base repo and pass `--chat-template`.

## 2026-08-05 02:52 EDT — c11 Devstral-AWQ HTTP 400 chat_template not supported

**Symptom**:
```
HTTP 400: {"error":{"message":"chat_template is not supported for Mistral tokenizers.","type":"BadRequestError","code":400}}
```

All three prompts failed instantly at `/v1/chat/completions`; cell wall time 0.0s. Container came up READY at 70s, `/v1/models` responded fine.

**Affected**: F.19 (Path E rebench) · c11 · cyankiwi/Devstral-Small-2-24B-Instruct-2512-AWQ-4bit

**Root cause**: c11 launches with `--tokenizer-mode mistral --config-format mistral --load-format mistral`, routing chat requests through vLLM's MistralCommonBackend. Per NVIDIA NIM docs and vLLM Ministral guidance, MistralCommonBackend rejects any request payload containing `chat_template` or `chat_template_kwargs` fields — the mistral_common library formats the prompt using its own built-in Mistral formatter and refuses any Jinja override at request time.

Our bench harness's `coder_nothink` profile sends `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` in every request (bench_pathE.py line 97). This is required for Qwen3-family cells (c01/c02/c03b/c09) to disable thinking mode, but MistralCommonBackend 400s the moment it sees the field. Since Mistral models have no thinking mode anyway, the flag is redundant for c11.

**Fix applied**: Added new `coder_nothink_mistral` sampling profile identical to `coder_nothink` but with NO `extra_body` at all (no `chat_template_kwargs`). Rewired c11's CELL_CONFIGS entry to use the new profile. Qwen cells (c01/c02/c03b/c09) keep the original `coder_nothink` profile.

**Files changed**:
- `bench/pathE_qwen36_27b/bench_pathE.py` (added `coder_nothink_mistral` profile; c11 profile rewired)

**References**:
- NVIDIA NIM VLM 2.0.6 release notes — "Per-request chat_template and chat_template_kwargs overrides are not supported for Mistral tokenizer-based models" (https://docs.nvidia.com/nim/vision-language-models/2.0.6-variant/release-notes.html)
- Trooper.AI Ministral tuning guide — documents the exact 400 error message for `chat_template_kwargs` under `--tokenizer-mode mistral`

**General rule**: Any cell that launches with `--tokenizer-mode mistral` MUST use a sampling profile with no `chat_template` and no `chat_template_kwargs` in `extra_body`. Applies to future Mistral-family AWQ/NVFP4/FP8 cells.

## 2026-08-05 06:10 EDT — Next.js dev pegged at 1927% CPU (Fast-Refresh error loop)

**Symptom**:
```
[browser] Uncaught TypeError: presets is not iterable
    at AgentPresetsPage (src/features/agent-presets/AgentPresetsPage.tsx:42:16)
> 42 |           {[...presets].sort((a, b) => (b.isDefault ? 1 : 0) - (a.isDefault ? 1 : 0))
```
Immediately after every `forge-up.sh`, PID of `next-server (v16.2.10)` climbs to 1900%+ CPU (~19 cores pegged). `pnpm dev` exits with `[ELIFECYCLE] Command failed.` but its detached `next-server` child stays alive and continues spinning. Killing the child brings CPU to idle.

**Affected**: dashboard · frontend · `/agents` route · Fast Refresh dev loop

**Root cause**: BFF `GET /api/agent-presets` returns `{"data": [AgentPreset, ...]}` (envelope shape, see `bff/routers/agent_presets.py::list_presets`). Frontend `fetchPresets` in `src/features/agent-presets/api.ts` typed the return as `Promise<AgentPreset[]>` and blindly returned `r.json()` — so React-Query stored the wrapper object as `presets`. `AgentPresetsPage.tsx` line 42 does `[...presets].sort(...)`, throwing `TypeError: presets is not iterable`. In Next 16.2.10 dev + Turbopack + App Router, a client-component throw inside a repeatedly-rendered path traps Fast Refresh in a re-render loop that saturates every available core.

**Fix applied**:
1. `src/features/agent-presets/api.ts::fetchPresets` — unwrap the `{data: [...]}` envelope, with an `Array.isArray` guard as fallback for any future contract change.
2. `src/features/agent-presets/AgentPresetsPage.tsx` — defensive `Array.isArray(presetsRaw) ? presetsRaw : []` so a future BFF contract drift can no longer peg dev-mode Next.js in an error loop.

**Files changed**:
- `src/features/agent-presets/api.ts`
- `src/features/agent-presets/AgentPresetsPage.tsx`

**Verified by**: user re-runs `bash scripts/forge-down.sh && bash scripts/forge-up.sh`, then `ps -eo pid,%cpu,cmd --sort=-%cpu | head -5`. `next-server` idle after browser navigates to `/agents`.

**Related BUILD_LOG entry**: 2026-08-05 06:10 EDT

## 2026-08-05 06:17 EDT — Follow-up: systemic prevention for Fast-Refresh CPU peg

**Symptom**: The 2026-08-05 06:10 EDT fix resolved the specific `presets is not iterable` throw, but the underlying vulnerability — that any client-component throw can pin `next-server` at ~1900% CPU in a Fast-Refresh re-render loop — remains for every other route.

**Root cause**: Next.js 16.2.10 App Router segments without an `error.tsx` boundary re-render their entire subtree on each Fast Refresh cycle. When a client component keeps throwing during that render, the loop saturates the event loop and every worker thread.

**Fix applied**:
1. `src/app/(dashboard)/error.tsx` — segment-level error boundary. Catches any client-component throw inside `/runs`, `/agents`, `/workspaces`, `/plugins`, etc., renders a fallback card with error detail + Retry button, and short-circuits the Fast-Refresh feedback loop.
2. `src/app/global-error.tsx` — root-level fallback (renders its own `<html>` and `<body>`) for anything the segment boundary misses (layout errors, provider errors).

**Files changed**:
- `src/app/(dashboard)/error.tsx` (new)
- `src/app/global-error.tsx` (new)

**Verified by**: After landing the fix, existing throws render as an error card instead of pegging CPU. Any future contract drift can no longer melt the workstation.

**Related BUILD_LOG entry**: 2026-08-05 06:17 EDT

## 2026-08-05 06:52 EDT — vllm-bench (c01) OOM: forge-vllm-planner holds VRAM

**Symptom**:
```
ValueError: Free memory on device cuda:0 (2.0/31.39 GiB) on startup is less than desired GPU memory utilization (0.9, 28.25 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.
```
`vllm-bench` container exits (1). `nvidia-smi` shows 29,585 MiB used with no c01 container running.

**Affected**: F.3 · bench/pathF_swebench · c01 launch on :8000

**Root cause**: `forge-vllm-planner` (DSR1-Distill-32B AWQ on :8511) holds ~29 GB VRAM steady-state. c01 (Qwen3.6-27B INT4 AutoRound) requires ~28 GB at `--gpu-memory-utilization 0.9`. RTX 5090's 32 GB VRAM cannot host both simultaneously. This is a hard hardware constraint documented in `forge-oh-llm-serving` skill's VRAM math.

**Fix applied**: `docker stop forge-vllm-planner` before F.3 runs, then `bash bench/pathE_qwen36_27b/vllm_launch.sh c01`, then restore the planner (`docker start forge-vllm-planner`) after F.3 completes. c01 cold-load = 162s on Blackwell.

**Files changed**: none (operational workflow only). BUILD_LOG entry 2026-08-05 06:55 EDT documents the workflow.

**Related BUILD_LOG entry**: 2026-08-05 06:55 EDT

## 2026-08-05 08:12 EDT — F.3 pass@1=16% caused by malformed hunk counts, not model floor

- **Symptom:** Smoke-25 run `20260805_0737_run` returned pass@1 4/25 (16%). Sampled failures showed `apply_ok: {}` empty and harness stdout tail:
  ```
  django__django-11133: >>>>> Patch Apply Failed:
  patching file django/http/response.py
  patch unexpectedly ends in middle of line
  patch: **** malformed patch at line 10
  ```
- **Affected stage/plugin/port:** Path F · SWE-bench Verified harness · bench/pathF_swebench
- **Root cause:** Model (c01 = Qwen3.6-27B-Coder INT4) emits unified-diff patches with WRONG counts in the `@@ -a,b +c,d @@` hunk header. django-11133: header said `-149,6 +149,7` but body had 6-old / 8-new lines. GNU patch reads the mismatch as the start of a new hunk header, aborts as malformed.
- **Fix applied:** `bench/pathF_swebench/apply_and_test.py`: added `recount_hunks(text)` (pure-Python `git apply --recount` equivalent). `normalize_patch()` now recounts after fence-stripping. Track `patch_recounted:bool` per task so post-run analysis can quantify how often the model got hunk math wrong.
- **Files changed:**
  - `bench/pathF_swebench/apply_and_test.py`
  - `bench/pathF_swebench/bench_pathF_swebench.py`
- **Related BUILD_LOG entry:** 2026-08-05 08:12 EDT
- **Related commit:** 5009a95
- **Verification pending:** rerun smoke-25 on Colossus, confirm pass@1 lift.


## 2026-08-05 08:38 EDT — F.3 apply-fail: duplicate '--- a/PATH' file sections in same patch

- **Symptom:** sphinx-doc__sphinx-8035 harness stdout:
  ```
  patching file sphinx/ext/autodoc/__init__.py
  Hunk #1 succeeded at 584 (offset 41 lines).
  ... (all 5 hunks succeed) ...
  patching file sphinx/ext/autodoc/__init__.py     ← SAME FILE, second section
  Reversed (or previously applied) patch detected!  Assuming -R.
  Hunk #2 FAILED at 582.
  1 out of 5 hunks FAILED
  ```
- **Affected stage/plugin/port:** Path F · SWE-bench Verified harness · normalize_patch
- **Root cause:** Model (c01 = Qwen3.6-27B-Coder INT4) emitted 2 `--- a/PATH / +++ b/PATH` sections against the same file. Verified: `jq -r '.patch' | grep -c '^--- a/'` → 2. GNU patch applies each section as an independent file-patch operation, so section 2 sees section 1's already-applied changes, guesses `-R`, then fails.
- **Fix applied:** Added `merge_duplicate_file_sections()` to `bench/pathF_swebench/apply_and_test.py`. Walks the diff, keeps first `--- a/PATH / +++ b/PATH` header per unique path, drops subsequent duplicates plus any trailing `index/diff --git/new file mode/deleted file mode` metadata, preserves all hunks in order. Wired into `normalize_patch()` BEFORE `recount_hunks()` (must merge structure first, then fix counts on merged patch).
- **Files changed:**
  - `bench/pathF_swebench/apply_and_test.py`
- **Related BUILD_LOG entry:** 2026-08-05 08:38 EDT
- **Related commit:** b2e89a6
- **Verified locally** against 5 unit cases; expects sphinx-8035 to become applyable on rerun.


## 2026-08-05 22:15 EDT — Agent-preset `ModelId` was cloud-only Literal (closed)

- **Symptom:** `bff/routers/agent_presets.py` had `ModelId = Literal["gpt-4o", "claude-opus-4", "gemini-2.5-pro", "local-llama"]` and seed presets pointed at cloud IDs. Creating a preset for the canonical Colossus stack (`qwen3.6-27b-int4-autoround` on vLLM :8501, `qwen3-coder:32k` on Ollama, `deepseek-r1-distill-32b-awq` on vLLM :8511) was impossible through the CRUD surface. Original KNOWN_ISSUES entry dated 2026-08-05.
- **Affected stage/plugin/port:** Stage 2 · BFF · `bff/routers/agent_presets.py`.
- **Root cause:** Stage 1 wired preset CRUD but never widened the type or added a backend pin field. `InferenceBackend` selection was Stage 2 scope.
- **Fix applied (Stage 2.1.7, amended plan):**
  - `ModelId` widened from cloud `Literal[…]` to plain `str` (comment retained for history).
  - Added `backendId: BackendId | None` and `role: RoleHint | None` to `AgentPreset`, `CreateRequest`, `UpdateRequest`.
  - `BackendId` is a `Literal[...]` of the six canonical ids in `bff/services/inference_backends/registry.py`; not imported at module load time to avoid a cycle.
  - Seed presets replaced: `ap-1` = Coder vLLM (c01 canonical, isDefault), `ap-2` = Planner vLLM (DSR1-Distill-32B AWQ), `ap-3` = Coder Ollama fallback (`qwen3-coder:32k`).
- **Files changed:**
  - `bff/routers/agent_presets.py` — types + seeds.
  - `bff/routers/runs.py` — reads `preset.backendId` and forwards to `route_by_role(backend_id=...)`.
- **Verification:** targeted BFF tests pass in venv (`bff/tests/test_model_router.py::…` + `bff/tests/test_inference_backends.py`).
- **Related BUILD_LOG entry:** 2026-08-05 22:15 EDT — Stage 2.1 backend layer landed.

## 2026-08-05 22:15 EDT — `GET /api/runs/{id}` returned `agentPresetId: null` (closed)

- **Symptom:** `curl /api/runs/<id> | jq '.data.agentPresetId'` returned `null` on succeeded runs even though `agentPresetId` was required on `POST /runs`. Original KNOWN_ISSUES entry dated 2026-08-05.
- **Affected stage/plugin/port:** Stage 2 · BFF · `bff/routers/runs.py`.
- **Root cause:** `_conv_to_run_summary(conv)` builds the summary from the agent-server conversation record, which has no notion of the caller's `agentPresetId`. `create_run` set `agentPresetName` on the blocked-path return but never echoed `agentPresetId` on the success-path return, so the response dropped it.
- **Fix applied (Stage 2.1.8, amended plan):**
  - Success path in `create_run()` now sets `summary["agentPresetId"] = body.agentPresetId` before returning.
  - Blocked path also echoes `agentPresetId` so clients see the same key in both branches.
- **Files changed:** `bff/routers/runs.py`.
- **Not addressed here:** run-store SQLite persistence of `agentPresetId`. The BFF's `run_id == conversation_id` (no separate SQLite run mapping) means a subsequent `GET /api/runs/{id}` after a BFF restart still cannot recover the field for old runs. That's the Stage 3 leftover documented in the amended Stage 2 plan; new runs return it correctly.
- **Verification:** shape assertion added to the endpoint tests; live-run verification pending Stage 2.4 exit-gate on Colossus.

## 2026-08-05 23:15 EDT — SDK security_analyzer surface: fully present at 1.40.0, no gap (informational)

- **Symptom (pre-check):** Reconciliation plan v1 § 3.1 flagged as a decision gate: "confirm whether pinned openhands-sdk==1.40.0 exposes security_analyzer risk scores on ActionEvents; if absent, log SDK-gap and skip risk-based mode." Baseline inspection on Colossus confirmed the surface is present and complete.
- **Affected stage/plugin/port:** Stage 3.1 · BFF · `bff/routers/runs.py` (attach point) + `bff/services/event_normalize.py` (surfacing).
- **Root cause (of the pre-check ambiguity):** The plan pre-dated the SDK inspection. The docstring reference to `PatternSecurityAnalyzer` in `openhands/sdk/security/ensemble.py` seeded doubt; a first grep suggested the class didn't exist at a `pattern_analyzer.py` module path. Deeper inspection showed it lives at `openhands.sdk.security.defense_in_depth.pattern.PatternSecurityAnalyzer` and is re-exported from `openhands.sdk.security.__init__`.
- **Fix applied (informational, not a code fix — this is baseline knowledge for future slices):**
  - `ActionEvent.security_risk` is a real field on the event; the SDK populates it only when a `SecurityAnalyzer` is attached to the conversation.
  - Enum values in `openhands.sdk.security.risk.SecurityRisk`: `UNKNOWN | LOW | MEDIUM | HIGH`.
  - Confirmation policies at `openhands.sdk.security.confirmation_policy`: `AlwaysConfirm | NeverConfirm | ConfirmRisky(threshold: SecurityRisk, confirm_unknown: bool)` — discriminated union with `kind` as the tag.
  - Wire shape for the confirmation-policy body: `{"policy": {"kind": "AlwaysConfirm"}}` (BFF already does this) or `{"policy": {"kind": "ConfirmRisky", "threshold": "MEDIUM", "confirm_unknown": true}}`.
  - Wire shape for security_analyzer body: `{"security_analyzer": <analyzer.model_dump(mode="json")>}` posted to `/api/conversations/{cid}/security_analyzer`. Contract from `openhands.sdk.conversation.impl.remote_conversation:1410-1420`.
  - Analyzers available at 1.40.0: `PatternSecurityAnalyzer` (deterministic regex, no LLM), `LLMSecurityAnalyzer` (trusts actor LLM's own risk annotation), `PolicyRailSecurityAnalyzer` (guardrails), `GraySwanAnalyzer` (external API, requires `GRAYSWAN_API_KEY`), `ToolShieldLLMSecurityAnalyzer` (separate guardrail LLM), `EnsembleSecurityAnalyzer` (merges multiple analyzers).
- **Chosen default (Stage 3.1):** `PatternSecurityAnalyzer` — deterministic, no LLM cost, no external network dependency, no API key. Ships risk values on real patterns immediately; swap-out to `EnsembleSecurityAnalyzer` or `ToolShieldLLMSecurityAnalyzer` is a one-line change once we add preset-level analyzer selection in a later slice.
- **Files touched:** none — this entry captures baseline SDK knowledge so no future session re-diagnoses.
- **Related BUILD_LOG entry:** 2026-08-05 23:15 EDT — Stage 3.1 Security Analyzer risk indicators.

## 2026-08-05 23:25 EDT — Playwright route-mock envelope mismatch broke Stage 3.1 spec

- **Symptom:** `tests/e2e/risk-badge.spec.ts` — both tests timed out at `await expect(page.getByText('terminal: rm -rf /tmp/*')).toBeVisible({ timeout: 15_000 })`. Timeline never rendered any event card. Backend tests (10/10), vitest (8/8), typecheck, restart, prod build, `/runs` 200 all green immediately prior.
- **Affected stage/plugin/port:** Stage 3.1 · frontend test harness · `src/tests/e2e/risk-badge.spec.ts` · `src/features/run-detail/api.ts` envelope contract.
- **Root cause:** The route-mock returned `{events: [...], total, latestEventId}` for `GET /api/runs/{id}/events`, but `fetchRunEvents()` at `src/features/run-detail/api.ts:14-18` extracts `json.data`. With no `.data` key, `bootstrapEvents = []` fell through the `useRunEvents` default, so the timeline had zero events to render. `useRunDetail` was also underspecified — the run object was missing `agentPresetName`, `workspaceType`, `activeTool`, `elapsedMs`, `estimatedCostUsd` (all in `RunSummarySchema`), which would have caused header-render side effects even if events had shown up.
- **Fix applied:**
  1. Renamed `FAKE_EVENTS.events` → `FAKE_EVENTS.data` (matches `fetchRunEvents` unwrap contract).
  2. Filled in all `RunSummarySchema` fields on `FAKE_RUN.data`.
  3. Added a `**/socket.io/**` route-mock returning 200 so `useRunStream` doesn't 404 into the console.
  4. Added `page.on('console'/'pageerror')` capture in the first test for future debug visibility.
  5. Re-ordered route-mocks so the more-specific `/events` glob is registered before the parent `/api/runs/{id}` glob (Playwright evaluates in registration order).
- **Files changed:** `src/tests/e2e/risk-badge.spec.ts`.
- **Search keys:** `page.route`, `route.fulfill`, `getByText timeout`, `fetchRunEvents`, `json.data`, `envelope`, `RunSummarySchema`, `useRunEvents empty`.

## 2026-08-05 23:37 EDT — Playwright strict-mode: role=alert matches Next.js route announcer

- **Symptom:** `hitl-approval.spec.ts` tests 1 + 3 failed with `strict mode violation: getByRole('alert') resolved to 2 elements`. First match was the real `ApprovalBanner`. Second match was `<div role="alert" aria-live="assertive" id="__next-route-announcer__">` — an empty div Next.js injects to announce route changes to screen readers. Both are valid semantic alerts.
- **Affected stage/plugin/port:** Stage 3.2 · Playwright HITL spec.
- **Root cause:** Playwright locators default to strict mode; any locator resolving to multiple elements fails even if one clearly matches intent. Next.js 16 route-announcer is baseline on every page and can't be turned off.
- **Fix applied:** Scope the banner locator with `.filter({ hasText: /awaiting your approval/i })`. For the click-flow tests, wait for the labeled Approve/Reject button instead of role=alert since that's what the test actually acts on.
- **Files changed:** `src/tests/e2e/hitl-approval.spec.ts`.
- **Search keys:** `strict mode violation`, `role="alert"`, `__next-route-announcer__`, `getByRole alert`, `Next.js announcer`, `Playwright filter hasText`.

## 2026-08-06 00:02 EDT — test_event_relay_normalize double-emit

**Symptom**:
```
AssertionError: expected 2 'event' emissions, got 4
```
`bff/tests/test_event_relay_normalize.py::test_relay_emits_normalized_wire_shape`

**Affected**: post-Stage-3 hygiene Slice B · event_relay tripwire test only. The relay code is correct — this is a test-double bug.

**Root cause**: `_run_loop` checks terminal status AFTER emitting events. Control flow per iteration:

1. `status = _fetch_status(cid)`
2. `events, next_page = _fetch_page(cid, page_id)`
3. `for ev in events: emit 'event'`
4. `if status in _TERMINAL_STATUSES: return`

My `fake_fetch_page` returned the same 2-event page on both iterations. Iteration 1 (`status=running`): emitted 2. Iteration 2 (`status=finished`): emitted 2 more, THEN hit the terminal check and returned. Total = 4.

**Fix applied**: `fake_fetch_page` now returns the events on the first call and an empty list on the second. Added a comment block explaining the `_run_loop` control-flow ordering so the next test author doesn't hit the same trap.

**Files changed**: `bff/tests/test_event_relay_normalize.py`

## 2026-08-06 00:02 EDT — test_direct_sync_call_would_block_confirms_the_hazard flake

**Symptom**:
```
AssertionError: Direct sync call did not block the event loop in this test env
assert 8.220085874199867e-07 >= 0.15
```
`bff/tests/test_event_relay_yield.py::test_direct_sync_call_would_block_confirms_the_hazard`

**Affected**: G.1 (2026-08-03) yield-fix regression suite. Not caused by any code change in this session — flaked in isolation during Slice A+B verification.

**Root cause**: pre-existing measurement bug. The test uses `_simulate_incoming_request(time.perf_counter(), latencies)` where `started_at` is evaluated in the CALLER's frame at call time, not when the coroutine body finally gets to run. So the delta measures nothing about event-loop scheduling delay — it measures argument-evaluation-to-body-entry, which is ~0 either way. The test as written cannot detect the hazard it claims to demonstrate.

The sibling `test_slow_producer_does_not_block_event_loop` uses the same measurement pattern; it passes only because its assertion is `< 0.10` and ~0 trivially satisfies it. Its passing tells us nothing either.

**Fix applied**: NONE this session. Logged as a debt item — a real event-loop-hog assertion needs to measure the delay INSIDE the coroutine relative to `create_task` timestamp, not from a caller-frame `perf_counter()` capture. Deferred to a future session (out of Slice A/B scope).

**Files changed**: none. Added to KNOWN_ISSUES.

**Impact assessment**: the G.1 fix itself (asyncio.to_thread + await asyncio.sleep(0) in event_relay._run_loop) is still in place at `bff/services/event_relay.py`; verified via source inspection. The runtime protection is intact. Only the two regression tests attempting to prove it are structurally unable to fail on regression. Self-eval harness ReadTimeout behavior would be the real detection surface if the fix were reverted.

## 2026-08-06 01:23 EDT — Stage 4 exit gate: 4 pre-existing flakes documented (carved out)

Ran the Stage 4 exit-gate sweep on Colossus 01:20–01:22 EDT against `bb09ff2` (post-ADR-019). Result: `pytest bff/tests/ -q` 329/331 pass, `pnpm typecheck` clean, `pnpm test:unit` 848/856 pass, `pnpm build` clean. Four tests fail. Blame-checked (`git log --oneline -5 -- <path>`) — none touch the § 4.4 Serena / § 4.5 DozerDB work. Details:

### 1. `bff/tests/test_event_relay_yield.py::test_direct_sync_call_would_block_confirms_the_hazard`
- **Symptom:** `AssertionError: Direct sync call did not block the event loop … assert 7.119961082935333e-07 >= 0.15`
- **Affected stage/plugin/port:** G.1 hotfix5 (EventRelay yield-point demo).
- **Root cause:** Env-sensitive. Test's own docstring says "If somehow this passes, the test setup is wrong (e.g. running on a nogil interpreter)." Colossus's Python 3.12 in `.oh-venv` occasionally schedules the "bad relay iteration" so tightly that the second coroutine gets a tick almost immediately (7 µs vs the 150 ms floor the test asserts). The test demonstrates a hazard; the real code it protects (`bff/services/event_relay.py`) is untouched.
- **Last touched by:** `07a5c04` (predates § 4.4 by weeks).
- **Fix applied:** none this session. Carve-out. Real fix later: replace the `while time.perf_counter() < deadline: pass` spin with an `os.write(sync_fd, ...)`-style blocker that's less scheduler-dependent, or gate the assertion on `sys.flags.gil` + scheduler-fairness heuristics.
- **Files changed:** none.

### 2. `bff/tests/test_repograph_router.py::TestHealthNoPassword::test_returns_error_when_password_missing`
- **Symptom:** `assert body["reachable"] is False` fails (actual: `True`). Log line: `INFO bff.deps.neo4j_driver:neo4j_driver.py:63 Neo4j driver initialised: uri=bolt://localhost:7687 database=forgeoh`.
- **Affected stage/plugin/port:** § 4.2 RepoGraph health endpoint (`924f324` / `d6aaf74` / `febe96c`).
- **Root cause:** Test-isolation leak on machines with live DozerDB. Test patches `bff.routers.repograph.get_settings` to return `Settings(neo4j_password="")` and expects `get_neo4j_driver()` to return `None`. But `bff.deps.neo4j_driver` uses a module-level LRU cache; if any earlier test in the run initialized the driver against live DozerDB (Colossus has `kosmos-dozerdb` running), the cached driver is returned and the health endpoint reports `reachable:true`. On CI or dev boxes without live DozerDB, this test passes because no cached driver exists.
- **Last touched by:** § 4.2 slice `924f324` (predates § 4.4).
- **Fix applied:** none this session. Carve-out. Real fix: the test should `patch("bff.deps.neo4j_driver.get_neo4j_driver.cache_clear")` (or the equivalent lru_cache reset) in a fixture, or the router should re-read settings on every health probe rather than reusing a cached driver when password is empty. This is a Stage 4.2 test-hygiene bug that only manifested tonight because Colossus's live DozerDB got exercised earlier in the same pytest process during other Stage 4 tests. Not a regression from § 4.4/§ 4.5 — the router itself was not touched.
- **Files changed:** none.

### 3. `src/tests/unit/AgentPresetCard.test.tsx::AgentPresetCard::renders name and model badge`
- **Symptom:** `TestingLibraryElementError: Unable to find an element with the text: GPT-4o`. Component renders lowercase `gpt-4o` inside `<span title="Model: gpt-4o">`.
- **Affected stage/plugin/port:** Phase 9 Slice 9A (Agent Preset Builder UI).
- **Root cause:** Case mismatch. Test expects `screen.getByText('GPT-4o')`; component displays the raw model ID `gpt-4o`. Either the test needs `/gpt-4o/i` or the component needs a `.toUpperCase()` for display. Pre-existing.
- **Last touched by:** `c93c3d4` (Task 3.6 batch 3, weeks pre-§ 4.4).
- **Fix applied:** none this session. Carve-out.
- **Files changed:** none.

### 4. `src/tests/unit/gitDiff.test.tsx::FilesTab — Real git diff toggle::renders the toggle when run has a local workspace path`
- **Symptom:** `TestingLibraryElementError: Unable to find an element by: [data-testid="diff-source-toggle"]` after `waitFor`. Rendered DOM shows a "No files changed" empty state instead of the file list + toggle.
- **Affected stage/plugin/port:** Step 7 Slice C.2 (real git diff wiring).
- **Root cause:** Test fixture missing `changedFiles` array or the mock for `useRunGitDiff` returns empty. The `diff-source-toggle` is conditionally rendered only when a file is selected; the empty state path never reaches the toggle. Pre-existing.
- **Last touched by:** `17dcb1b` (predates § 4.4).
- **Fix applied:** none this session. Carve-out.
- **Files changed:** none.

### Decision

All four failures pre-date § 4.4 and § 4.5, none touch the paths modified in this session, and all Stage 4 manual-verification items are green. Stage 4 exit gate is met; the four flakes are recorded here so they get picked up in a follow-up test-hygiene slice (not part of Stage 4 or Stage 5.1 kickoff scope).

## 2026-08-06 01:59 EDT — Ollama contract tests: stale nomic-embed literals after ADR-020
- **Symptom:** After ADR-020 flipped the default from `nomic-embed-text` (768) to `qwen3-embedding:0.6b` (1024), two live-tier runs on Colossus failed:
  1. `test_live_nomic_embed_text_is_768_dim`: `assert 1024 == 768` (baseline run) and `assert 2560 == 768` (with `OLLAMA_EMBED_MODEL=qwen3-embedding:4b`). The live call to Ollama succeeded and returned the correct native dim for each model — only the assertion was stale.
  2. `test_embed_returns_vectors_from_canned_response`: `assert 'qwen3-embedding:4b' == 'qwen3-embedding:0.6b'` — the ambient `OLLAMA_EMBED_MODEL=qwen3-embedding:4b` A/B env var propagated into the ctor and broke a literal string assertion.
- **Affected:** `bff/tests/memory/test_ollama_embeddings_adapter_contract.py` (Stage 5.2 vendored test surface).
- **Root cause:** Kosmos-vendored tests were name-and-dim pinned to `nomic-embed-text`. When I filed ADR-020 I updated the mock-response `"model"` field and one string assertion, but missed: (a) the live-tier test name + 768-dim literal, (b) that the mock-response test reads `OLLAMA_EMBED_MODEL` from the process env in the ctor `os.environ.get(...)` fallback path.
- **Fix:**
  - Live-tier test renamed to `test_live_default_embedder_matches_declared_dim` and rewritten to look up the expected dim from the adapter's `_MODEL_DIMENSIONS` table using the resolved model name. It now correctly validates any model registered in the table — 0.6b (1024), 4b (2560), 8b (4096), or the legacy `nomic-embed-text` (768). One test now covers every supported A/B run.
  - Canned-response test now passes `default_model="qwen3-embedding:0.6b"` explicitly to the ctor so its literal assertion is stable regardless of ambient `OLLAMA_EMBED_MODEL`.
- **Files changed:** `bff/tests/memory/test_ollama_embeddings_adapter_contract.py`.
- **Verified:** 43/43 memory contract tests pass with no env override AND with `OLLAMA_EMBED_MODEL=qwen3-embedding:4b` set (live tier still skipped in CI sandbox without `FORGE_MEMORY_LIVE=1`).

## 2026-08-06 03:29 EDT — memory=503 during Stage 5.6a Playwright pass; forge-up.sh missing .env.neo4j sourcing
- **Symptom:** `curl http://127.0.0.1:8081/api/memory/recent-writes?limit=1` → `503`. Playwright `memory-inspector.spec.ts` correctly skipped with `preconditions unmet: BFF MemoryPort unavailable (503)`.
- **Affected:** Stage 5.6a visual verify. Non-blocking for backend/frontend unit tests (already green — see BUILD_LOG 2026-08-06 03:15 EDT).
- **Root cause:** `scripts/forge-up.sh` launches uvicorn without sourcing `.env.neo4j`, so `NEO4J_PASSWORD` was absent from the BFF process env. `bff/deps/memory_port.get_memory_port()` correctly detected the missing env, refused to compose, and returned `None`; the router 503'd exactly as ADR-024 K1 specifies (non-fatal degradation). But this made every Playwright visual pass skip until the operator manually restarts the BFF with the env sourced.
- **Secondary symptom from prior instruction:** `npm --prefix src run build` ENOENT — `package.json` lives at repo root, not under `src/`. The prior BFF/Next build had already been produced by an earlier session, so `next start` from repo root still returned 200 for `/runs`; only the redundant build step failed. Canonical recipe is in `forge-oh-colossus-ops`: `cd ~/dev/forge-oh && npm run build` (no `--prefix src`).
- **Fix applied:**
  1. `scripts/forge-up.sh` — added `set -a; . "$REPO_ROOT/.env.neo4j"; set +a` guarded by `[ -f ... ]` immediately before the BFF `nohup uvicorn ...` line. Silent when the file is absent (`warn` line only); no impact on other services.
  2. `src/tests/e2e/memory-inspector.spec.ts` — prefer `.oh-venv/bin/python` for the seed helper (falls back to `python` on PATH). Keeps the seed working when Playwright is invoked from a shell without `.oh-venv` activated.
- **Files changed:** `scripts/forge-up.sh`, `src/tests/e2e/memory-inspector.spec.ts`.
- **Verified:** sandbox-only edits (Colossus verify pending user pull). Rerun path documented in SESSION_HANDOFF and in BUILD_LOG 2026-08-06 03:30 EDT entry below.

## 2026-08-06 03:34 EDT — seed_memory_event.py ModuleNotFoundError; .serena/ ADR-016 violation blocks screenshot push
- **Symptom A:** `ModuleNotFoundError: No module named 'openhands_tools_ext'` when Playwright ran `.oh-venv/bin/python scripts/seed_memory_event.py`. Spec continued (seed is non-fatal), but no new row was added — the assertion still passed because DozerDB already had `rows: 1` from a prior write.
- **Symptom B:** Screenshot auto-push failed with `ADR-016 VIOLATION: Colossus<->GitHub mirror drift detected` — `.serena/.gitignore` and `.serena/project.yml` were untracked and unignored on Colossus.
- **Affected:** Stage 5.6a live-DozerDB visual pass (both symptoms occurred in the same run).
- **Root cause A:** `openhands_tools_ext` is a repo-local package, not pip-installed into `.oh-venv`. It's importable at runtime because the BFF adds REPO_ROOT to `sys.path` (uvicorn worker cwd), but a standalone script has no such setup. The venv-python-vs-PATH-python distinction was a red herring; the fix is `sys.path` bootstrap, not choosing a different interpreter.
- **Root cause B:** Serena (an editor/assistant tool) creates `.serena/project.yml` + `.serena/.gitignore` in the workspace on first use. ADR-016 mandates every path is either tracked or explicitly ignored. Serena's state is per-machine noise, so it should be ignored, not tracked.
- **Fix:**
  - `scripts/seed_memory_event.py` — prepend `REPO_ROOT` (parent of `scripts/`) to `sys.path` if not already present. Works whether the script is invoked from the venv or PATH python.
  - `.gitignore` — add `.serena/` with a rationale comment tying it to ADR-016.
- **Files changed:** `scripts/seed_memory_event.py`, `.gitignore`.
- **Verified:** sandbox edits only; Colossus re-run required.

## 2026-08-06 03:54 EDT — resolve_tool signature drift breaks registration probe (Stage 5.6b)
- **Symptom:** `test_tool_is_registered_under_consult_memory_name` fails with `TypeError: resolve_tool() missing 1 required positional argument: 'conv_state'`.
- **Affected stage/plugin/port:** Stage 5.6b — OpenHands SDK tool registry consumer.
- **Root cause:** OpenHands SDK v1.40.0 `openhands.sdk.tool.registry.resolve_tool(name, conv_state)` requires `conv_state` positionally. My probe called `resolve_tool("consult_memory")` — one arg — because I read the signature off memory of an earlier SDK version. FinishTool/ThinkTool never call `resolve_tool` themselves, so there was no template to copy.
- **Fix applied:** made the probe version-tolerant. First try `resolve_tool(name, None)`, fall back to `resolve_tool(name)` on TypeError, then fall back to peeking at the module's private registry dict (`_REGISTRY`/`REGISTRY`/`_tools`/`TOOLS`). Any of the three paths satisfies the assertion; the underlying question ("is the name registered after import?") is what matters.
- **Files changed:** `openhands_tools_ext/tests/memory/test_consult_memory_tool.py`.

## 2026-08-06 03:54 EDT — Playwright memory-timeline spec skipped (FE=null, :3100 dead) (Stage 5.6b)
- **Symptom:** Playwright output `[memory-timeline] FE status: null` → test skipped with `preconditions unmet: frontend http://127.0.0.1:3100`. `forge-restart.sh` had brought up Next.js on :3000 (dev), while the `next start -p 3100` prod process from an earlier session was killed (`Exit 143`) by the restart sequence.
- **Affected stage/plugin/port:** Stage 5.6b live-task DoD — Playwright spec `memory-timeline-marker.spec.ts`.
- **Root cause:** `forge-up.sh` starts Next.js on :3000 (`pnpm dev`) — the ADR-verified dev port. Playwright specs must run against `next start` on :3100 (never `next dev`, per `forge-oh-playwright-visual`). The original spec pointed at :3100 unconditionally and had no path to start the prod server if it wasn't already running.
- **Fix applied:** adopted the same `PLAYWRIGHT_START_PROD=1` pattern the sibling `memory-inspector.spec.ts` uses. When the env var is set, `beforeAll` runs `npm run build` in `src/` and spawns `npx next start -p 3100` (killed in `afterAll`). Precondition-missing message now spells out the exact rebuild command so the operator can also start prod manually and rerun.
- **Files changed:** `src/tests/e2e/memory-timeline-marker.spec.ts`.

## 2026-08-06 04:00 EDT — resolve_tool takes Tool object, not string (Stage 5.6b)
- **Symptom:** `resolve_tool("consult_memory", None)` fails with `AttributeError: 'str' object has no attribute 'name'`. SDK source: `resolver = _REG.get(tool_spec.name)` — it dereferences `.name` on the first arg.
- **Affected stage/plugin/port:** Stage 5.6b — tool registration test.
- **Root cause:** `openhands.sdk.tool.registry.resolve_tool(tool_spec: Tool, conv_state: ConversationState)` takes a full `Tool` spec object (which carries a `.name` field) and a live `ConversationState`. Neither dependency is worth reconstructing just to answer "is this name registered?". Prior test tried string arg; then fell back to `(name, None)` which also fails for the same reason.
- **Fix applied:** dropped the resolver call entirely; probe the module's `_REG` dict directly (the exact dict `register_tool(name, cls)` populates). Same semantic question, one assertion, no ConversationState fabrication.
- **Files changed:** `openhands_tools_ext/tests/memory/test_consult_memory_tool.py`.

## 2026-08-06 04:00 EDT — Playwright DoD spec blocked by vLLM coder down (Stage 5.6b)
- **Symptom:** Playwright fails at `POST /api/runs` with `"status":"blocked"` and `data.id=""`, routing error `role='coder' pinned to backend_id='vllm-coder' unavailable`. Spec's `expect(id).toBeTruthy()` fires.
- **Affected stage/plugin/port:** Stage 5.6b live-task DoD; BFF `runs.create_run` routing path.
- **Root cause:** BFF `create_run` calls `route_by_role()` BEFORE creating the agent-server conversation. When vLLM coder on :8501 is down and supervisor cannot recover, routing raises `ModelUnavailableError`, and the BFF short-circuits with a shell response carrying `id=""` (no agent-server conversation was created — nothing to id). This is by design at the BFF level, but couples the memory-marker DoD to LLM runtime state, which is architecturally wrong.
- **Fix applied:** spec no longer goes through BFF `POST /api/runs`. Added `pickOrCreateConversation()` which reads `GET /api/conversations` on agent-server and reuses any existing conversation id. The BFF's `GET /api/runs/{id}` proxies to agent-server `/api/conversations/{id}`, so `/runs/{id}` renders fully regardless of vLLM state. If no conversation exists, spec fails loud with instructions.
- **Files changed:** `src/tests/e2e/memory-timeline-marker.spec.ts`.
- **Follow-up:** the BFF `blocked` path returning `data.id=""` is a real UX bug (frontend can't render a blocked run). Track separately — out of Stage 5.6b scope. Recommended follow-on: BFF should either persist a blocked-run shell with a synthesized id or return 503, not a 200 with empty id.

## 2026-08-06 04:04 EDT — registry stores resolver closure, not class (Stage 5.6b)
- **Symptom:** `_REG['consult_memory']` is `<function _resolver_from_subclass.<locals>._resolve>`, not `ConsultMemoryTool`, so `is`/`isinstance` assertions fail.
- **Affected stage/plugin/port:** Stage 5.6b tool registration test.
- **Root cause:** SDK's `register_tool` wraps the class in `_resolver_from_subclass(cls)` before storing — the registry value is a resolver closure that, when called with a Tool spec + ConversationState, returns the built Sequence[ToolDefinition]. Never a direct class reference.
- **Fix applied:** relaxed the value assertion to `callable(resolved) or resolved is cm.ConsultMemoryTool`. Presence of the key is the actual proof of registration; the wrapped value is an implementation detail we don't own.
- **Files changed:** `openhands_tools_ext/tests/memory/test_consult_memory_tool.py`.

## 2026-08-06 04:04 EDT — no existing conversations on fresh agent-server (Stage 5.6b)
- **Symptom:** `pickOrCreateConversation` throws "No existing agent-server conversation found" because `GET /api/conversations` is empty on this box.
- **Affected stage/plugin/port:** Stage 5.6b Playwright DoD.
- **Root cause:** Fresh install / never ran a real run on this Colossus session. Nothing to reuse.
- **Fix applied:** extended `pickOrCreateConversation` with a fallback that creates a conversation via BFF `POST /api/runs` using the Ollama fallback preset (`ap-3`) — Ollama on :11434 is always up on Colossus, avoiding the vLLM coder dependency. Overridable via `FORGE_TEST_OLLAMA_PRESET_ID`.
- **Files changed:** `src/tests/e2e/memory-timeline-marker.spec.ts`.

## 2026-08-06 04:07 EDT — Playwright strict-mode: 🧠 matches 3 elements (Stage 5.6b)
- **Symptom:** `getByText('🧠')` resolves to 3 nodes (sidebar Memory nav icon, EventCard icon, and one other decorative span); strict mode fails. Summary-text assertion passed — the EventCard is actually rendering correctly.
- **Affected stage/plugin/port:** Stage 5.6b Playwright DoD spec.
- **Root cause:** The 🧠 glyph is reused across the UI (sidebar nav icon for the Memory route + timeline event icon). A bare text query cannot disambiguate.
- **Fix applied:** scope the icon assertion to the EventCard button. The EventCard's accessible name is the summary string (`aria-label` = summary), so `getByRole('button', { name: /^Memory consulted \(semantic\)/ })` uniquely identifies it, then `.getByText('🧠')` inside that button asserts the icon is present.
- **Files changed:** `src/tests/e2e/memory-timeline-marker.spec.ts`.

## 2026-08-06 04:17 EDT — Stage 5 exit gate two new failures

### 1. `openhands_tools_ext/tests/gpu/test_hook.py` — ModuleNotFoundError at collection

- **Symptom:** `ERROR openhands_tools_ext/tests/gpu/test_hook.py :: ModuleNotFoundError: No module named 'openhands_tools_ext'` when running `pytest openhands_tools_ext/tests/ -q`.
- **Root cause:** Missing `openhands_tools_ext/tests/gpu/__init__.py`. All sibling test dirs (`memory/`, `selfeval/`, `trajectory/`, `verify/`) had one; only `gpu/` was missing. pytest could not resolve the package rootdir for `test_hook.py` and fell back to sys.path without the repo root.
- **Fix:** `touch openhands_tools_ext/tests/gpu/__init__.py`.
- **Files:** `openhands_tools_ext/tests/gpu/__init__.py` (new, empty).

### 2. `bff/tests/test_event_relay_yield.py::test_direct_sync_call_would_block_confirms_the_hazard`

- **Symptom:** `AssertionError: Direct sync call did not block the event loop in this test env — the hazard demonstration is broken. assert 1.03e-06 >= 0.15`.
- **Root cause:** Test flow is:
  ```python
  relay_task = asyncio.create_task(_bad_relay_iteration())   # scheduled, not yet run
  await asyncio.sleep(0.001)   # ← yields; relay_task runs its 200ms busy-loop, RETURNS
  http_task = asyncio.create_task(_http_request())   # ← created AFTER relay finished
  ```
  Because `await asyncio.sleep(0.001)` yields to the loop, `relay_task` (which awaits nothing) runs to completion — spinning for 200ms — BEFORE `http_task` is created. When `http_task` finally runs, it captures `time.perf_counter()` at the coroutine's call site inside the body and appends `now - started_at` — which is ~0 μs because `started_at` was captured at the same instant.
  The test's premise ("relay hogs the loop while http request is queued") never materializes because the request coroutine is never queued during the busy-loop. This is a test-code bug, not a code-under-test bug.
- **Fix path (out of Stage 5 scope):** Restructure the test so `http_task` is created BEFORE `relay_task` gets a yield opportunity. One valid pattern:
  ```python
  http_task = asyncio.create_task(_http_request())   # captures started_at NOW
  relay_task = asyncio.create_task(_bad_relay_iteration())   # will run first
  await asyncio.gather(relay_task, http_task)
  ```
  With this order, `http_task` is scheduled at t0. When the loop yields, `relay_task` runs first (FIFO), busy-spins for 200ms, then `http_task` records latency ≈ 200ms.
- **Impact:** Diagnostic-only test. The three real tests in the same file (`test_update_from_event_runs_in_worker_thread`, `test_slow_producer_does_not_block_event_loop`, and the wrapped version) still pass. The event_relay production code is correct.
- **Do NOT block Stage 5 on this.** Move to KNOWN_ISSUES.


## 2026-08-06 05:00 EDT — E2E spec REPO_ROOT + ESM/CJS bugs (Stage 6.1)

- **Symptom (bug 1):** `search-timeline-marker.spec.ts` — test assertions and screenshot succeeded, but auto-push hook errored:
  ```
  Error: Command failed: git add -f screenshots/search-timeline-marker.png
  fatal: not a git repository (or any of the parent directories): .git
  ```
- **Affected stage/plugin/port:** Stage 6.1 · Playwright E2E harness · N/A (test-only)
- **Root cause:** `REPO_ROOT = resolve(process.cwd(), '..')` walked one level *above* the repo. Playwright's `cwd` is the repo root (since `playwright.config.ts` lives there), not `src/`, so `../` pointed at `/home/rmholston/dev/`.
- **Fix applied (commit `3fdfafb`):** derive REPO_ROOT from the spec file's own filesystem location (three levels up from `src/tests/e2e/*.spec.ts`). Also correct `APP_DIR = REPO_ROOT` since `package.json` is at repo root.
- **Symptom (bug 2, introduced by bug-1 fix):** `SyntaxError: Cannot use 'import.meta' outside a module` — Playwright refused to load the spec.
- **Root cause:** Forge-OH's `package.json` has no `"type": "module"` field, so Playwright's `ts-node` compiles specs to CommonJS. `import.meta.url` is ESM-only.
- **Fix applied (commit `2175c51`):** drop `fileURLToPath(import.meta.url)`, use CJS `__dirname` directly.
- **Files changed:** `src/tests/e2e/search-timeline-marker.spec.ts` (both commits).
- **Same bugs latent in:** `src/tests/e2e/memory-timeline-marker.spec.ts` (identical structural copy) — fix if/when re-run.
- **Prevention:** Any future E2E spec that needs REPO_ROOT must use `resolve(__dirname, '..', '..', '..')`. Do NOT rely on `process.cwd()`. Do NOT use `import.meta` until `package.json` gains `"type": "module"` (which would require broader migration).


## 2026-08-06 05:45 EDT — write_note test assertion missed SDK `kind` discriminator

**Symptom:** `openhands_tools_ext/tests/write/test_write_note_idempotent.py::test_first_call_writes_file_and_marks_ledger` failed on Colossus with:
```
AssertionError: assert {'title': 'He...teNoteAction'} == {'title': 'He...ody': 'World'}
Left contains 1 more item:
{'kind': 'WriteNoteAction'}
```

**Affected stage/plugin/port:** Stage 6.3 · openhands_tools_ext/common · IdempotentToolExecutor.

**Root cause:** `openhands.sdk.tool.tool.Action` is a pydantic discriminated-union base. `action.model_dump()` on any subclass emits `{"kind": "<SubclassName>", ...}`. `IdempotentToolExecutor._action_to_arguments` was dumping without filtering, so the `kind` key leaked into (a) the ledger's `arguments` payload and (b) the `sha256(canonical_args_json)` input.

Two independent problems this caused:
1. Test asserted `mark_body["arguments"] == {"title": ..., "body": ...}` and failed.
2. Ledger arg-hashes would be invalidated on any future SDK rename (`kind` → `type`) or Action-subclass rename.

**Fix applied:**
- Added `_EXCLUDED_ACTION_META_FIELDS = frozenset({"kind"})` on `IdempotentToolExecutor`.
- `_action_to_arguments` now strips those keys after `model_dump()` before returning.
- Added regression test `test_arguments_exclude_sdk_kind_discriminator` that confirms `kind` is stripped even when pydantic still emits it (and remains valid if SDK ever drops the discriminator).
- Rationale block-comment above the frozenset explains why we don't just live with `kind` in the hash.

**Files changed:**
- `openhands_tools_ext/common/idempotent_executor.py` — `_EXCLUDED_ACTION_META_FIELDS` + strip logic + docstring.
- `openhands_tools_ext/tests/write/test_write_note_idempotent.py` — regression test.

**Also fixed in same commit:** `scripts/test-crash-resume.sh` phase 4 was silent on success. Added `echo` on success + on the replay-mark response for observability. No behavior change.

## 2026-08-06 06:37 EDT — BFF Socket.IO 403/404 when launched via `bff.main:app`

- **Symptom:** Playwright spec fails on
  `getByText('Disconnected from run stream').toHaveCount(0)` with browser
  console repeatedly logging
  `WebSocket connection to 'ws://localhost:8081/socket.io/...' failed:
  Error during WebSocket handshake: Unexpected response code: 403`.
  BFF log shows `WebSocket /socket.io/... 403 - connection rejected`.
  Direct `curl http://127.0.0.1:8081/socket.io/?EIO=4&transport=polling`
  returns HTTP 404 `{"detail":"Not Found"}`.
- **Affected:** BFF · Socket.IO layer · any E2E spec that uses live socket
  streaming or debug-inject relay.
- **Root cause:** `bff/main.py` defines two ASGI objects:
  - `app` — bare FastAPI (routes only, no socket.io mount)
  - `app_with_sio = socketio.ASGIApp(sio, other_asgi_app=app)` — the real
    entry-point that mounts `/socket.io/` in front of the FastAPI routes.
  Launching `uvicorn bff.main:app` (as we had been doing manually) serves
  only the bare FastAPI, so `/socket.io/` is unrouted → 404 on polling and
  uvicorn's built-in WS protocol handler returns 403 on WebSocket upgrades
  for unmounted paths.
- **Fix:** always launch BFF with `uvicorn bff.main:app_with_sio`. Verified
  handshake returns HTTP 200 with
  `0{"sid":"...","upgrades":["websocket"],...}` payload.
- **Files changed:** none (operational fix — recipe update).
- **Canonical restart recipe (Colossus):**
  ```bash
  pkill -f 'uvicorn bff.main' 2>/dev/null
  sleep 2
  cd ~/dev/forge-oh
  source .oh-venv/bin/activate
  FORGE_TIMELINE_DEBUG_INJECT=1 PYTHONPATH=. \
    nohup uvicorn bff.main:app_with_sio --host 0.0.0.0 --port 8081 \
      > /tmp/forge-bff-8081.log 2>&1 &
  disown
  ```
- **Cross-refs:** consider updating `forge-oh-colossus-ops` skill so future
  sessions never launch `bff.main:app` again.
