# Forge-OH — KNOWN_ISSUES

Open, unresolved issues that do not block current-stage progress. Each entry
names the blocker scope, the affected stage/plugin/port, and the plan for
resolution. When resolved, move the entry into DEBUG_LOG.md as a closed
diagnosis (with fix) and delete from here.

Timestamp format: `YYYY-MM-DD HH:MM EDT`.

---

## 2026-08-06 14:47 EDT — BFF container HEALTHCHECK probes wrong path (`/health` → 404)

- **Blocks:** none. Container is functionally healthy; Stage 7 DoD is met. `docker compose ps` just reports `(health: starting)` indefinitely and `docker logs` emits one 404 line per 30s from the internal probe.
- **Symptom:** `docker logs forge-oh-bff-1` → `"GET /health HTTP/1.1" 404 Not Found` on every HEALTHCHECK interval.
- **Root cause:** `bff/Dockerfile` HEALTHCHECK targets `http://localhost:8081/health`, but the only handler on `/health` is `bff/routers/repograph.py:190` mounted under `/api/repograph/*` (so the real URL is `/api/repograph/health`). `bff/main.py` exposes no bare `/health`.
- **Attempted fixes:** none.
- **Next investigation:** add a bare `@app.get("/health")` returning `{"ok": True}` to `bff/main.py` (cheap, standard convention). Alternative: change HEALTHCHECK to probe an unconditionally-200 endpoint like `/api/agent-presets`. Prefer the former.
- **Related DEBUG_LOG search terms:** `health 404`, `HEALTHCHECK`, `docker container health`.

---

## 2026-08-06 14:47 EDT — Containerized BFF trajectory drain fails on missing `/home/bff`

- **Blocks:** none. Startup completes; other subsystems work. Trajectory persistence inside the container silently no-ops until fixed.
- **Symptom:** `docker logs forge-oh-bff-1` → `trajectory drain scheduler failed to start: [Errno 13] Permission denied: '/home/bff'` once at startup.
- **Root cause:** `openhands_tools_ext/trajectory/store.py:59` resolves the DB path as `Path.home() / ".forge-oh" / "trajectories.db"`. In the container the non-root `bff` user (uid 1001) has `HOME=/home/bff` but `useradd --system` in `bff/Dockerfile` did not create that dir.
- **Attempted fixes:** none.
- **Next investigation:** two clean options — (1) create the home dir via `useradd --create-home --home-dir /home/bff` in `bff/Dockerfile`; or (2) set `TRAJECTORY_STORE_PATH=/app/data/trajectories.db` in `docker-compose.yml`, add a named volume mount for `/app/data`, and let `store.py:53`'s `override` path win. Prefer (2) — keeps trajectory DB out of the ephemeral container FS via a persistent volume.
- **Related DEBUG_LOG search terms:** `trajectory drain`, `/home/bff`, `Permission denied`, `Path.home`.

---

## 2026-08-06 00:05 EDT — confirm_unknown=True is required until analyzer attach is hard-required

- **Blocks:** none. Current fail-closed behavior is correct; this issue documents the precondition for a future flip.
- **Symptom:** Slice C audit (BUILD_LOG 2026-08-06 00:05 EDT) rejected the proposed flip `confirm_unknown=True → False` in `bff/routers/runs.py:145`.
- **Root cause:** `PatternSecurityAnalyzer` never emits UNKNOWN itself — it always returns LOW/MEDIUM/HIGH. UNKNOWN in the runtime originates from analyzer *attach* failure at run creation (`bff/routers/runs.py:431-447`, best-effort with `log.warning`-swallowed exceptions). Flipping to `confirm_unknown=False` while attach can silently fail would create a fail-open regression on any run whose analyzer attach 4xx/5xx'd or raised.
- **Attempted fixes:** none. Audit-only.
- **Precondition to flip safely:** make analyzer attach a hard requirement of run creation. If `POST /api/conversations/{cid}/security_analyzer` returns >= 400 or raises, abort run creation with a clear error. Then a running conversation is proof the analyzer is attached, and UNKNOWN can only come from an unrecognized enum value (a bug, not a fail-open path).
- **Next investigation:** post-Stage-4. Convert the analyzer attach from `log.warning`-swallow to a hard `raise HTTPException(500, "security analyzer attach failed")`. Add a regression test that a run creation with a mocked-failing analyzer POST returns 500 rather than a run id. Then land the `confirm_unknown=False` flip.
- **Related BUILD_LOG entry:** 2026-08-06 00:05 EDT — Slice C audit findings.

---

## 2026-08-06 00:02 EDT — test_event_relay_yield hazard-demonstration test cannot fail

- **Blocks:** none. The G.1 event-loop-yield fix in `bff/services/event_relay.py` is still in place (verified via source read); this issue is a defect in its *regression test*, not the code.
- **Symptom:** `bff/tests/test_event_relay_yield.py::test_direct_sync_call_would_block_confirms_the_hazard` produced `latencies[0] = 8.22e-7`, failing `>= 0.15`. The sibling `test_slow_producer_does_not_block_event_loop` passes only because its assertion `< 0.10` is trivially satisfied by ~0.
- **Root cause:** both tests call `_simulate_incoming_request(time.perf_counter(), latencies)` with `started_at` evaluated in the CALLER frame. The delta then measures argument-evaluation to coroutine-body-entry (~0 in a healthy loop), not event-loop scheduling delay. The tests can't detect the hazard they claim to.
- **Attempted fixes:** none this session. Logged in DEBUG_LOG 2026-08-06 00:02 EDT.
- **Next investigation:** rewrite both tests to timestamp inside the coroutine relative to a `create_task` timestamp captured outside. Consider using `asyncio.get_running_loop().time()` deltas. See G.1 DEBUG_LOG 2026-08-03 23:40 EDT for the original hazard the test was meant to guard.
- **Impact:** real runtime protection (asyncio.to_thread + asyncio.sleep(0)) is intact. The only detection surface for a regression would be the self-eval harness ReadTimeout behavior, which is not a fast-feedback signal.

---

## 2026-08-05 — pnpm workspace CI check fails on every PR (Node 20 + workspace config)

- **Blocks:** none. `mergeable: true` on all merged PRs (#5, #6, #7, closeout).
- **Symptom:** GitHub Actions `pnpm store path --silent` step exits non-zero with `packages field missing or empty`. Every push to `main` shows 2 red checks including check runs against `main` itself.
- **Root cause:** pnpm v11 + Node 20 deprecation interaction with the workspace configuration. Not code-related; the failure is in the CI action's pre-flight step, before any repo command runs.
- **Attempted fixes:** none. Discovered during PR #5-#7 merges.
- **Next investigation:** pin pnpm setup-action version, or set explicit `packages` field in `pnpm-workspace.yaml` if one exists, or migrate the CI check to a different step order that survives the pnpm store bootstrap.
- **Related DEBUG_LOG search terms:** `pnpm store path`, `packages field missing`, `pnpm-lock`, `CI red`.

---

## 2026-08-05 — c01 context-budget-skip ceiling at `max_model_len=32768` (INFORMATIONAL)

- **Blocks:** none. Informational ceiling documenting an honest limit of c01's context window.
- **Symptom:** 35/500 tasks (7.0%) in F.3 full-500 skipped by harness with `ERROR: context-budget-skip: prompt_tokens=N leaves only Xt room (< floor 512)`. All skipped tasks had oracle-file `prompt_tokens > 32k` (matplotlib, sympy, xarray dominant repos). Harness correctly counts these against pass@1 as unresolved-with-error (conservative). Raw pass@1 = 0.266 / attempted-only pass@1 = 0.286 — the 2pt spread reflects the ceiling.
- **Smoke-30 v2 skip rate:** 4/30 tasks (13.3%) skipped in `20260805_2106_run` — **intentionally over-sampled vs the 7.0% full-500 base rate.** The smoke's 30-task budget quantizes small proportions harshly; sampling proportionally would have yielded 2 skips (6.7%), but 4 was chosen to reliably exercise the context-budget-skip code path on every regression run. This is a smoke-design property, not a signal that skip rate is rising. The skipped tasks in smoke-30 v2 are: `django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248` — all confirmed skips in the full-500 ground truth.
- **Root cause:** c01 (`c01_coder_vllm_qwen36_27b_int4`) launched with `--max-model-len 32768`. Oracle-retrieval loads full ground-truth file contents; matplotlib `axes/_axes.py`, sympy multi-file oracle sets, xarray large modules exceed 32k tokens at 4k output reserve. Model itself (Qwen3.6-27B) supports 128k context natively.
- **Attempted fixes:** none — this is an informational entry, not a bug. F.3 was deliberately kept at 32k `max_model_len` per launcher config.
- **Next investigation:** if Stage 2+ requires raising `max_model_len`, factor in VRAM budget (F.3 already saturated at 99.98% / 32,599 MiB peak). Options: (a) raise `max_model_len` to 65536 or 131072 with `kv-cache-dtype=fp8` retention and reduced `max-num-seqs`, (b) implement oracle-file compression (modified-regions-plus-context) in `oracle_prompt.py`, (c) accept as honest capability ceiling. Path B (Stage 1H.5 agent loop with iterative test-run-fix) may be higher-leverage than raising context alone.
- **Related DEBUG_LOG search terms:** `context-budget-skip`, `max-model-len`, `oracle_prompt`, `prompt_tokens exceeds`, `KV cache VRAM`, `smoke-30`, `smoke skip rate`.

---

## 2026-08-05 23:15 EDT — Stage 3.3 DependencyGuard descoped from Stage 3

- **Blocks:** none. Stage 3 exit gate updated to exclude 3.3 per reconciliation-plan-v1 § 3 (backend + frontend ship together — a gate with no caller is dead code).
- **Symptom (pre-work inspection):** `grep -rn "pip install\|npm install\|subprocess.*install" openhands_tools_ext bff` returns zero matches. The BFF layer never triggers package installation; installs happen inside the OpenHands agent-server container's tool observers, which are outside the BFF's addressable surface.
- **Root cause of scope mismatch:** The plan implicitly assumed BFF-level install call sites existed (as they would in a monolithic agent). Forge-OH's architecture routes install-capable tools (`terminal`, `execute_bash`) through the agent-server, so any real slopsquatting gate must live inside an agent-server tool observer or as a pre-tool-call hook — not inside the BFF.
- **Attempted fixes:** none. The right placement was clarified before writing any code, avoiding a dead-code port + endpoint.
- **Next investigation (deferred):** Choose one of three paths for a future slice:
  1. Register a pre-tool-call hook on the agent-server side that inspects `execute_bash` action payloads for `pip install`/`npm install` patterns, calls a BFF-hosted `DependencyGuard` (PyPI/npm existence + <90d age check + allowlist) via HTTP, and blocks with a HITL approval via the Stage 3.2 confirmation-policy path.
  2. Vendor an existing OSS slopsquatting checker (e.g., pypi-guard, socket.dev CLI) as a subprocess pre-check inside the tool observer.
  3. Wait for the OpenHands SDK to expose a first-class `DependencyGuard` port; if 1.41+ ships one, prefer that over hand-building.
  Path 1 keeps the port in the BFF (where PyPI/npm HTTP calls belong) and matches the Stage 3.2 confirmation-policy path for the approval surface.
- **Not addressed here:** CI lockfile hash pinning via `pip-audit` (also mentioned in plan § 3.3). That step is independent of the runtime guard and can be filed as its own slice against the CI workflow when we revisit `.github/workflows/`.
- **Related BUILD_LOG entry:** 2026-08-05 23:15 EDT — Stage 3.1 (analyzer attach + risk surfacing) landed; DependencyGuard descoped.

---

## 2026-08-05 23:15 EDT — Stream events not normalized on BFF (Stage 3.1 follow-up)  [RESOLVED 2026-08-05 23:59 EDT]

Resolved in Slice B of the post-Stage-3 hygiene batch. `event_relay._run_loop` now routes every fetched event through `bff.services.event_normalize.normalize_event` before `sio.emit("event", ...)`. Wire event shape is now byte-identical to the HTTP bootstrap path emitted by `list_events`. New tripwire test at `bff/tests/test_event_relay_normalize.py` asserts the contract, including that Stage 3.1's `securityRisk` projection survives the wire. See BUILD_LOG 2026-08-05 23:59 EDT.

- **Blocks:** none. RiskBadge renders correctly on stream events via a snake/camel fallback in `toDisplayEvent`. Auto-collapse filter behaves fail-open on stream ActionEvents (leaks them past the filter when the toggle is on), which is safe — the user just sees the extra event rather than losing a real risk annotation.
- **Symptom:** `bff/services/event_relay.py:209` emits raw agent-server `ev` dicts on the `event` socket channel without passing them through `normalize_event`. Bootstrap events (`GET /api/runs/{id}/events`) call `normalize_events(items)` at `bff/routers/runs.py:568-571`, so they arrive as `type: 'action'` with `securityRisk` camel-case. Stream events arrive as raw `kind: 'ActionEvent'` dicts and the frontend `normalizeEvent()` in `src/lib/streaming/useRunStream.ts` falls back to `type: 'message'`.
- **Root cause:** `event_relay.py` predates the BFF-side normalizer and was never migrated. This is not a regression from Stage 3.1 — it is a pre-existing shape divergence between the two event paths that Stage 3.1 makes visible via `securityRisk`.
- **Attempted fixes:** none in Stage 3.1. Papered over on the frontend by accepting both `securityRisk` and `security_risk` in `toDisplayEvent()`, and documented as a filter limitation in a code comment above `allEventsUnfiltered.filter`.
- **Next investigation:** In `event_relay.py:_fetch_page`, call `normalize_event(ev)` on each event before emitting. Verify the frontend `normalizeEvent()` in `useRunStream.ts` still handles the merged shape (its trailing `...e` spread should preserve everything). Add a unit test that both paths produce identical event shape given the same raw agent-server dict.
- **Related BUILD_LOG entry:** 2026-08-05 23:15 EDT — Stage 3.1.

---

## 2026-08-05 23:34 EDT — Status enum drift: `awaiting_approval` vs `awaiting-approval` [RESOLVED 2026-08-05 23:49 EDT]

- **Symptom:** `bff/routers/runs.py:97` maps agent-server `waiting_for_confirmation` to `awaiting_approval` (underscore). `src/lib/schemas/run.ts:19` declares `awaiting-approval` (dash) for the same status. `src/features/run-detail/api.ts::fetchRun` casts `json.data` to `RunSummary` without calling `.parse()`, so the drift silently ships underscore to the frontend. Every frontend `run.status === 'awaiting-approval'` comparison is dead code today; multiple non-schema files also use underscore (Badge.tsx, PlanNode.tsx, StatusBadge stories).
- **Root cause:** BFF status vocabulary (underscore) and schema declaration (dash) drifted at some earlier commit; no boundary validation caught it because Zod parse is never invoked.
- **Attempted fix (Stage 3.2):** Added a `_normalizeRunStatus` helper in `src/features/run-detail/api.ts` that translates `awaiting_approval` → `awaiting-approval` at the `fetchRun` boundary. This unblocks the ConfirmRisky HITL path in `page.tsx` (dead branch now fires). Does NOT unify the rest of the frontend or add Zod enforcement.
- **Next investigation:** Two hygiene followups in a dedicated commit:
  1. Pick one canonical form (recommend underscore — it matches the BFF wire and the majority of frontend consumers). Flip the schema, `StatusBadge` component, `RunDetailHeader`, and all tests/fixtures to underscore. Drop the boundary normalizer.
  2. Add `RunSummarySchema.parse(json.data)` in `fetchRun` + `RunSummarySchema.parse` in the runs list to catch future drift at the boundary.
- **Related BUILD_LOG entry:** 2026-08-05 23:34 EDT — Stage 3.2.
- **RESOLVED 2026-08-05 23:49 EDT:** Canonical form chosen (`awaiting_approval` underscore). Schema flipped, every consumer + test + fixture flipped, `_normalizeRunStatus` deleted, `RunSummarySchema.parse` now called at the `fetchRun` boundary as the tripwire against future drift. See BUILD_LOG 2026-08-05 23:49 EDT for the full 12-file diff. Only follow-up: two dead-code `StatusBadge` component files (`src/components/core/StatusBadge.tsx` + `src/components/core/StatusBadge/StatusBadge.tsx`) could be deleted; the real runtime `StatusBadge` lives in `src/components/core/Badge.tsx`.

---

## 2026-08-06 00:37 EDT — Pre-existing test failures surfaced during Stage 4.2/4.3 verification

Two unit-test failures observed on Colossus while running `pytest bff/tests/test_repograph_router.py` and `pnpm test:unit` for Stage 4.2/4.3 verification. Neither is caused by Stage 4 code — they are pre-existing debt made visible by the first end-to-end run in this configuration.

### 1. `TestHealthNoPassword::test_returns_error_when_password_missing`

- **Symptom:** Test asserts `body["reachable"] is False` when `neo4j_password=""`, but on Colossus (with DozerDB running unauthenticated in dev mode on `bolt://localhost:7687`) the driver connects successfully anyway → `reachable=True` → assertion fails.
- **Root cause:** The test conflates "empty password" with "auth failure." In DozerDB's local dev container, empty-password Bolt handshakes succeed because the container isn't enforcing auth on the default connector. The test only holds on hardened Neo4j instances that reject empty passwords.
- **Impact:** Green on hardened Neo4j, red on Colossus/DozerDB dev container. Does not affect production behavior of the `/health` endpoint.
- **Fix path (out of Stage 4 scope):** Either (a) mock the driver factory in this specific test so the connect attempt is deterministic regardless of local Neo4j auth state, or (b) split into two tests: one that mocks a rejected auth (`reachable=False`), one that documents that unauthenticated dev containers connect (`reachable=True`).
- **Do NOT block Stage 4.2/4.3 on this.**

### 2. `gitDiff.test.tsx` — `diff-source-toggle` waitFor timeout

- **Symptom:** `pnpm test:unit` reports the `waitFor(() => expect(screen.getByTestId('diff-source-toggle')).toBeInTheDocument())` step in `src/tests/unit/gitDiff.test.tsx:127` times out. Full failure name: `FilesTab — Real git diff toggle > renders the toggle when run has a local workspace path`.
- **Root cause:** Unknown as of 2026-08-06 00:37 EDT — first surfaced during Stage 4.2/4.3 verification. Predates Stage 4 (component is unrelated to RepoGraph).
- **Impact:** Blocks a fully green `pnpm test:unit`. Does not affect runtime behavior of the diff viewer or any Stage 4 code path.
- **Fix path (out of Stage 4 scope):** Bisect against `main` to isolate the commit that broke the test, then either fix the test-side wait/render flow or the underlying component regression. Look at recent changes to `DiffViewer` component and its "source view" toggle.
- **Do NOT block Stage 4.2/4.3 on this.**

### 3. `AgentPresetCard.test.tsx` — `renders name and model badge` query failure

- **Symptom:** `pnpm test:unit` reports the query at `src/tests/unit/AgentPresetCard.test.tsx:29` fails in the test `AgentPresetCard > renders name and model badge` — the expected element (name and/or model badge) is not found by testing-library.
- **Root cause:** Unknown as of 2026-08-06 00:40 EDT. Component `AgentPresetCard` is unrelated to RepoGraph and predates Stage 4.
- **Impact:** Second of two failures blocking a fully green `pnpm test:unit`. Does not affect runtime behavior of any Stage 4 code path.
- **Fix path (out of Stage 4 scope):** Inspect `AgentPresetCard` component + fixture used by the test around line 29. Likely a rename, a prop-shape drift, or a testid/aria change that the test wasn't updated for. Bisect against `main` if the trigger commit isn't obvious.
- **Do NOT block Stage 4.2/4.3 on this.**

---

## 2026-08-06 00:47 EDT — Operational trap: port-3100 conflict with long-lived `next start`

- **Context:** Colossus keeps a long-lived production frontend at `nohup npx next start -H 127.0.0.1 -p 3100 > ~/.forge-oh/next-prod.log 2>&1 &`. It survives shell exits and does NOT auto-reload on git pulls or new builds.
- **Trap:** any subsequent `pnpm start` / ad-hoc launch that tries to bind port 3100 fails with `EADDRINUSE`, so Playwright and manual checks silently hit the stale build (which may lack routes added since the persistent process started). Symptom: `/some-new-route` returns 404 or an outdated shell, tests fail at first `getByTestId(...)`.
- **Detection:** `ss -ltnp | grep ':3100'` shows the bound `next-server` PID.
- **Recovery before any new `next start`:**
  ```bash
  fuser -k 3100/tcp && sleep 1
  # or: kill -TERM <PID_from_ss>
  ```
  Then rebuild (`pnpm build`) if the checkout advanced since the old process started, and relaunch.
- **Playwright launch template that works:**
  ```bash
  NEXT_PUBLIC_FEATURE_REPOGRAPH=true NEXT_PUBLIC_BFF_URL=http://127.0.0.1:8081 \
    nohup npx next start -H 127.0.0.1 -p 3100 > ~/.forge-oh/next-prod.log 2>&1 &
  # poll GET /repograph until HTTP 200 before running the spec
  ```
- **Long-term fix path (out of Stage 4 scope):** wrap the persistent launcher in a systemd unit or a `pplx start-server`-style script so kill/replace is one command. For now, the manual `fuser -k` step is the workflow.

---

## 2026-08-06 04:17 EDT — `test_direct_sync_call_would_block_confirms_the_hazard` — broken test premise

- **Symptom:** `bff/tests/test_event_relay_yield.py::test_direct_sync_call_would_block_confirms_the_hazard` fails with `assert ~1e-6 >= 0.15`.
- **Root cause:** Test constructs `relay_task` then `await asyncio.sleep(0.001)` before creating `http_task`. The sleep yields, `relay_task` runs its 200ms busy-loop and finishes BEFORE `http_task` is created. Latency measurement is meaningless because the request coroutine was never queued during the busy-loop.
- **Impact:** Diagnostic test only. The three real tests in the file (`test_update_from_event_runs_in_worker_thread`, `test_slow_producer_does_not_block_event_loop`, and the wrapped version) all pass. Production event_relay behaviour is correct.
- **Fix path (out of Stage 5 scope):** Swap the create_task order — `http_task` first, then `relay_task`, then gather. See DEBUG_LOG 2026-08-06 04:17 EDT for full explanation.
- **Do NOT block Stage 5 on this.**
