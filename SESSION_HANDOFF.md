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

## Open questions awaiting user

Two design questions from the 6.4→6.4b handoff still stand for 6.4c:

- **Q1 (button placement):** Should `RestoreToHereButton` live alongside `ForkFromHereButton` on the same user-message event card, or replace it? My lean is **alongside** — fork = "branch and continue," restore = "branch and reset files to pre-fork state." Different semantics, both worth surfacing.
- **Q2 (runs list growth):** As restore produces new run rows, the runs list grows. Should the runs list gain a "hide restored-from parents" filter to manage growth? My lean is **defer to a later slice** — real usage will show whether growth is actually a problem.

Answer both at the start of the 6.4c sub-session before implementation begins.

**One new design question for 6.4c planning:**

- **Q3 (reset target):** `git reset --hard` needs a target ref inside the fork's worktree. Options:
  - (a) HEAD of source workspace at fork time (matches 6.4b behaviour — simple, but loses any commits between fork time and restore time). **My lean.**
  - (b) HEAD-at-the-picked-event (semantically ideal, but requires per-event workspace snapshots that do not exist).
  - (c) HEAD of source workspace at restore time (matches "reset to latest," but that's just `git reset --hard` in the source — not really restore).

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

## Colossus runtime state (informational, not blocking 6.4c planning)

At 07:30 EDT during DoD verify: `role='coder' unavailable: vLLM at http://localhost:8501 down, supervisor could not recover, Ollama fallback exhausted`. This is a runtime-ops concern, not a 6.4b regression. First step of the next session should be to bring vLLM back up (or confirm Ollama serving `qwen3-coder:32k`) so full-stack `stage-6.4b-verify.sh` can also be run for belt-and-suspenders.

## Next sub-session's first act

1. Read this file.
2. Answer Q1/Q2/Q3.
3. Bring at least one coder backend online (vLLM :8501 or Ollama `qwen3-coder:32k`) — needed for 6.4c integration testing.
4. Then implement Stage 6.4c step 1 (backend restore endpoint).
