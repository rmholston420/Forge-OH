# Forge-OH SESSION_HANDOFF

_Last updated: 2026-08-06 07:31 EDT_

## Current stage/plugin/port

- **Stage 6.4 — CLOSED (2026-08-06).** Fork-from-here on user-message events. Non-destructive. Fully verified.
- **Stage 6.4b — CLOSED (2026-08-06 07:31 EDT).** Per-run git worktrees. DoD met via primitive+wiring evidence.
- **Stage 6.4c — OPEN.** Restore-via-fork per ADR-025. Foundation from 6.4b is in place.

## What was completed this session

**Stage 6.4b close-out**
- `bff/services/worktree.py` (346 lines) — provision/remove/list primitives with WORKTREE_ROOT safety guards, name-collision handling, cleanup-on-failure semantics.
- `bff/tests/test_worktree_service.py` — 23 tests, all green.
- `bff/routers/runs.py` — create_run step 2.5 wired (A1 non-git log-and-pass-through, C1 rollback on agent-server failure or missing cid) + new dedicated `DELETE /api/runs/{run_id}` endpoint (B2) that reaps worktrees when path tail starts with `run-`.
- `bff/tests/test_runs_worktree.py` — 8 tests, all green.
- Read-path callers (event_relay, run_compare, metrics_aggregation) verified as no-op: all three pass `conv.workspace.working_dir` through unchanged, so step 2.5 makes them worktree-aware automatically.
- `scripts/stage-6.4b-verify.sh` — full-stack DoD verify (BFF + agent-server + LLM).
- `scripts/stage-6.4b-verify-direct.sh` — primitive-layer DoD verify (works when LLMs are down).
- Primitive-layer DoD verify passed on Colossus 2026-08-06 07:31 EDT: all 7 invariants green (provision × 2, `git worktree list` shows both, A/B/source isolation, `list_worktrees` sees both, both reaped cleanly, source repo `git worktree list` clean afterward).

## What remains before Stage 6.4c DoD

**DoD (from ADR-025 §Decision · Stage 6.4c):** `POST /api/runs/{run_id}/restore` composes `Conversation.fork()` + `git reset --hard` inside the new fork's isolated worktree. Original run untouched. UI surface reachable from a `RestoreToHereButton` on user-message event cards.

Ordered execution plan (next sub-session picks up here):

1. **Backend · restore endpoint.** New `POST /api/runs/{run_id}/restore` in `bff/routers/runs.py`. Body accepts optional `from_event_id` (same shape as the existing fork endpoint). Composition:
   - Call the existing internal fork logic (already parameterised on `from_event_id`) to produce a new run + isolated worktree.
   - Inside the new fork's worktree path, run `git reset --hard <base_ref>` to reset files to the pre-fork state.
   - Choice of `base_ref`: HEAD of the source workspace at fork time (matches how 6.4b provisions). Confirm this is the desired semantic; alternative is HEAD-at-the-picked-event, but that requires per-event workspace snapshots which do not exist.
2. **Backend · tests.** New `bff/tests/test_runs_restore.py`. Cover: restore happy path (returns new run with worktree, source unchanged), from_event_id honoured, `git reset --hard` actually ran (verify via marker file that gets reset), agent-server failure rolls back the worktree, source run's conversation untouched.
3. **Frontend · button + hook + test.** Mirror the fork-from-here pattern:
   - `restoreRun()` + `useRestoreRun` in `src/lib/api/runs.ts` + hooks.
   - `RestoreToHereButton` alongside `ForkFromHereButton` on user-message event cards. Gate behind same `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` flag (per Q2 in 6.4).
   - Unit test in `src/tests/unit/domain-RestoreToHereButton.test.tsx`.
4. **Frontend · Playwright E2E.** New spec: create run, wait for user message, click Restore, confirm new run appears with worktree isolation, confirm source run's file state unchanged.
5. **Colossus verify.** End-to-end restore against a live workspace with vLLM back up.
6. **Docs/logs.** BUILD_LOG close-out; SESSION_HANDOFF for the next stage.

## Design decisions locked (2026-08-06 07:34 EDT)

All three carry-over questions resolved. No open questions blocking 6.4c.

- **Q1 — Button placement: ALONGSIDE.** `RestoreToHereButton` sits next to `ForkFromHereButton` on user-message event cards. Both gated behind the same `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` flag. Rationale: fork = "branch and continue with current files," restore = "branch and reset files to pre-event state." Distinct semantics; users need both flows.
- **Q2 — Runs-list filter: DEFERRED.** No filter for "hide restored-from parents" this stage. Rationale: no evidence yet that runs-list crowding is a real problem. Revisit if real usage surfaces friction.
- **Q3 — Reset target: (a) HEAD at fork time.** Composition:
  1. `Conversation.fork(from_event_id=...)` produces the new run.
  2. `provision_worktree` checks out HEAD of source workspace at fork time (already 6.4b behaviour — no change needed).
  3. Inside the new fork's worktree: `git reset --hard HEAD` + `git clean -fd` to blow away any uncommitted files the agent staged mid-conversation.
  
  Rationale: the *purpose* of restore is to blow away the working-tree changes an agent accumulated mid-run so the user can try again from a clean file state. `git reset --hard HEAD` in the fresh worktree does exactly that. Option (b) would need per-event workspace snapshots that we deliberately deferred (ADR-025 §Rejected alternatives). Option (c) resets the *source*, not the fork — that's destructive edit, not restore.

## Verification summary (session-cumulative, all green on Colossus)

| Layer | Result |
|---|---|
| BFF fork pytests | 9/9 |
| Fork+idempotency+endpoints regression | 38/38 |
| Vitest `domain-ForkFromHereButton.test.tsx` | 10/10 |
| Vitest `gitDiff.test.tsx` | 5/5 |
| Vitest `AgentPresetCard.test.tsx` | 5/5 |
| Full `pnpm test:unit` | 874 passed, 6 skipped, 0 failed |
| `pnpm build` | clean |
| Playwright E2E fork-from-here | 1/1 in 1.3 s |
| **Stage 6.4b worktree service pytests** | **23/23** |
| **Stage 6.4b runs.py wiring pytests** | **8/8** |
| **Stage 6.4b targeted regression (worktree + wiring + fork)** | **39/39** |
| **Stage 6.4b full BFF suite** | **563 passed, 1 skipped, 2 pre-existing unrelated fails, 23 deselected** |
| **Stage 6.4b primitive-layer DoD (7 invariants)** | **all green** |

## Commits landed this session (chronological)

- Stage 6.4 close-out block preserved from prior handoff.
- `161039f` · Stage 6.4b ADR-025 + stage-6 companion doc + BUILD_LOG + SESSION_HANDOFF baseline
- `e325a3c` · Stage 6.4b step 1: `bff/services/worktree.py` + 23 unit tests
- `13f181b` · Fix: defer default WORKTREE_ROOT resolution to call time
- `3cf0d20` · Stage 6.4b step 2: wire worktree into runs.py (A1 + B2 + C1) + 8 tests
- `d4d1dd2` · Fix: DELETE /runs 204 signature (`response_class=Response`)
- `6734bdb` · BUILD_LOG step 2 close-out
- `b1ab27c` · Stage 6.4b step 3: verified-no-op close-out
- `0898f95` · Stage 6.4b step 6: DoD verification script (full-stack)
- `4efead1` · Stage 6.4b verify: tolerate bare-list workspaces payload
- `514563f` · Stage 6.4b verify: default to Ollama preset (ap-3)
- `0f52b34` · Stage 6.4b: primitive-layer DoD verify script
- (this commit) · Stage 6.4b CLOSED · BUILD_LOG + SESSION_HANDOFF

## Colossus runtime state (07:43 EDT: coder backend LIVE)

**Resolved.** vLLM coder is serving on :8000 via container `vllm-bench` (up 25+ hours). BFF was dialing :8501 with the wrong served-name — added two overrides to `~/dev/forge-oh/.env`:

```
LLM_CODER_URL=http://localhost:8000
LLM_CODER_MODEL=c01_coder_vllm_qwen36_27b_int4
```

Verified via `POST /api/runs` (ap-1) → `status=queued`, `routing.selected="vllm/c01_coder_vllm_qwen36_27b_int4"`, `routing.baseUrl="http://localhost:8000/v1"`. Cleanup `DELETE /api/runs/{id}` → 204. Both create and delete paths work end-to-end. See BUILD_LOG.md 2026-08-06 07:43 EDT for full triage + a follow-up item to reconcile the container's port/served-name with BFF defaults so operators don't need `.env` overrides.

**Nothing blocking 6.4c.** Backend unit tests + full-stack integration tests can both proceed.

## Next sub-session's first act

1. Read this file.
2. Q1/Q2/Q3 already locked — skip to implementation.
3. Confirm coder backend is still up: `bash scripts/vllm-coder-status.sh` (should show `vllm-bench` container up on :8000 with `c01_coder_vllm_qwen36_27b_int4`). If not, `bash scripts/vllm-coder-fix-env.sh` re-verifies + re-persists.
4. Implement Stage 6.4c step 1 (backend `POST /api/runs/{run_id}/restore` endpoint).
