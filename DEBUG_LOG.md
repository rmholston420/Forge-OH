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
