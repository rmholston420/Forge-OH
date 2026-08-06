# Forge-OH — KNOWN_ISSUES

Open, unresolved issues that do not block current-stage progress. Each entry
names the blocker scope, the affected stage/plugin/port, and the plan for
resolution. When resolved, move the entry into DEBUG_LOG.md as a closed
diagnosis (with fix) and delete from here.

Timestamp format: `YYYY-MM-DD HH:MM EDT`.

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

## 2026-08-05 23:15 EDT — Stream events not normalized on BFF (Stage 3.1 follow-up)

- **Blocks:** none. RiskBadge renders correctly on stream events via a snake/camel fallback in `toDisplayEvent`. Auto-collapse filter behaves fail-open on stream ActionEvents (leaks them past the filter when the toggle is on), which is safe — the user just sees the extra event rather than losing a real risk annotation.
- **Symptom:** `bff/services/event_relay.py:209` emits raw agent-server `ev` dicts on the `event` socket channel without passing them through `normalize_event`. Bootstrap events (`GET /api/runs/{id}/events`) call `normalize_events(items)` at `bff/routers/runs.py:568-571`, so they arrive as `type: 'action'` with `securityRisk` camel-case. Stream events arrive as raw `kind: 'ActionEvent'` dicts and the frontend `normalizeEvent()` in `src/lib/streaming/useRunStream.ts` falls back to `type: 'message'`.
- **Root cause:** `event_relay.py` predates the BFF-side normalizer and was never migrated. This is not a regression from Stage 3.1 — it is a pre-existing shape divergence between the two event paths that Stage 3.1 makes visible via `securityRisk`.
- **Attempted fixes:** none in Stage 3.1. Papered over on the frontend by accepting both `securityRisk` and `security_risk` in `toDisplayEvent()`, and documented as a filter limitation in a code comment above `allEventsUnfiltered.filter`.
- **Next investigation:** In `event_relay.py:_fetch_page`, call `normalize_event(ev)` on each event before emitting. Verify the frontend `normalizeEvent()` in `useRunStream.ts` still handles the merged shape (its trailing `...e` spread should preserve everything). Add a unit test that both paths produce identical event shape given the same raw agent-server dict.
- **Related BUILD_LOG entry:** 2026-08-05 23:15 EDT — Stage 3.1.

---

## 2026-08-05 23:34 EDT — Status enum drift: `awaiting_approval` vs `awaiting-approval`

- **Symptom:** `bff/routers/runs.py:97` maps agent-server `waiting_for_confirmation` to `awaiting_approval` (underscore). `src/lib/schemas/run.ts:19` declares `awaiting-approval` (dash) for the same status. `src/features/run-detail/api.ts::fetchRun` casts `json.data` to `RunSummary` without calling `.parse()`, so the drift silently ships underscore to the frontend. Every frontend `run.status === 'awaiting-approval'` comparison is dead code today; multiple non-schema files also use underscore (Badge.tsx, PlanNode.tsx, StatusBadge stories).
- **Root cause:** BFF status vocabulary (underscore) and schema declaration (dash) drifted at some earlier commit; no boundary validation caught it because Zod parse is never invoked.
- **Attempted fix (Stage 3.2):** Added a `_normalizeRunStatus` helper in `src/features/run-detail/api.ts` that translates `awaiting_approval` → `awaiting-approval` at the `fetchRun` boundary. This unblocks the ConfirmRisky HITL path in `page.tsx` (dead branch now fires). Does NOT unify the rest of the frontend or add Zod enforcement.
- **Next investigation:** Two hygiene followups in a dedicated commit:
  1. Pick one canonical form (recommend underscore — it matches the BFF wire and the majority of frontend consumers). Flip the schema, `StatusBadge` component, `RunDetailHeader`, and all tests/fixtures to underscore. Drop the boundary normalizer.
  2. Add `RunSummarySchema.parse(json.data)` in `fetchRun` + `RunSummarySchema.parse` in the runs list to catch future drift at the boundary.
- **Related BUILD_LOG entry:** 2026-08-05 23:34 EDT — Stage 3.2.
