# Forge-OH SESSION_HANDOFF

_Last updated: 2026-08-06 07:04 EDT_

## Current stage/plugin/port

- **Stage 6.4 — CLOSED (2026-08-06).** Fork-from-here on user-message events. Non-destructive. Fully verified.
- **Stage 6.4b — OPEN.** Per-run worktrees. Foundation for §2.4 concurrent worktree-agents AND for 6.4c restore.
- **Stage 6.4c — DEFERRED** until 6.4b lands. Restore-via-fork per ADR-025.

## What was completed this session (running total across all sub-sessions today)

**Stage 6.4 close-out**
- Fork-from-here verified across all four DoD layers (BFF fork pytests 9/9, regression 38/38, vitest `domain-ForkFromHereButton.test.tsx` 10/10, Playwright E2E 1/1 in 1.3 s, `pnpm build` clean).
- Q1/Q2/Q3 decisions logged.
- `forge-oh-colossus-ops` skill updated with the BFF Socket.IO handshake triage entry and corrected `bff.main:app_with_sio` module reference.

**Stage 7-C.2-hotfix close-out**
- `src/tests/unit/gitDiff.test.tsx` fixture drift fixed (RunSummarySchema hardened after slice C.2).
- `src/tests/unit/AgentPresetCard.test.tsx` stale model-badge assertion fixed.
- Full `pnpm test:unit` now clean: **874 passed, 6 skipped, 0 failed**.

**Stage 6.4b open (this sub-session)**
- Codebase inspection confirmed §6.4 spec prerequisites do not exist (see DEBUG_LOG.md 2026-08-06 06:59 EDT).
- ADR-025 authored (Proposed) — Restore via fork, not in-place `git reset` + conversation-state rewind.
- Stage-6 companion doc landed at `docs/reconciliation-plan-stage-6.md` with a STATUS NOTE prepended explaining the 6.4 → 6.4/6.4b/6.4c split.

## What remains before Stage 6.4b DoD

**DoD (from ADR-025 §Decision · Stage 6.4b):** two concurrent runs against the same workspace do not observe each other's file changes; `git worktree list` shows both worktrees; `run_compare` still works between per-run worktrees.

Ordered execution plan (next sub-session picks up here):

1. **Backend · worktree provisioning primitive.** Add `bff/services/worktree.py` exposing `provision_worktree(run_id, base_ref) → path` and `remove_worktree(run_id) → None` wrapping `git worktree add ${WORKTREE_ROOT}/<run_id> <base_ref>` and `git worktree remove`. Configurable `WORKTREE_ROOT` env (default `~/.forge-oh/worktrees/`). Safety guard: refuse to remove paths not under `WORKTREE_ROOT`.
2. **Backend · run lifecycle wiring.** In `bff/routers/runs.py`, on run creation:
   - Resolve `workspace.path` from agent-server workspace list (already there).
   - Call `provision_worktree(run_id, base_ref)` where `base_ref` is the workspace's current HEAD.
   - Pass the returned worktree path as `working_dir` in the `LocalWorkspace` payload to agent-server, instead of the workspace's shared path.
   - On run deletion (or explicit cleanup endpoint TBD), call `remove_worktree(run_id)`.
3. **Backend · read-path updates.** Point these at the per-run worktree path (they currently read `workspace.working_dir`, which will now be the worktree path automatically once step 2 lands — verify no double-resolution):
   - `bff/services/event_relay.py:_extract_working_dir`
   - `bff/services/run_compare.py:base_working_dir`/`fork_working_dir` resolution
   - `bff/services/metrics_aggregation.py` workspace fallbacks
4. **Backend · tests.** New `bff/tests/test_worktree_service.py` covering provision/remove happy path, `WORKTREE_ROOT` safety guard, double-provision idempotency (or explicit failure — pick one, document in the test). Extend `bff/tests/test_runs_create.py` to assert `working_dir` is a worktree path not a shared workspace path.
5. **Frontend.** Read-only "worktree" chip in run detail header showing the per-run worktree path (relative to `WORKTREE_ROOT`). Unit test.
6. **Colossus verify.** Two runs against the same workspace concurrently; write different content in each; confirm neither observes the other's files. `run_compare` between them still surfaces per-file diff.
7. **Docs/logs.** Append 6.4b close-out entry to BUILD_LOG.md; DEBUG_LOG.md entries for any new symptoms; overwrite SESSION_HANDOFF for 6.4c open.

## Open questions awaiting user

**None blocking Stage 6.4b implementation.** Two design questions to answer at 6.4b→6.4c transition (not now):

- Should `RestoreToHereButton` in 6.4c live alongside `ForkFromHereButton` on the same user-message event card, or replace it? (My lean: alongside, since fork and restore are semantically distinct — fork = "branch and continue," restore = "branch and start over with files reset.")
- Should the runs list in 6.4c gain a "hide restored-from parents" filter to manage growth? (Deferred to 6.4c planning.)

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

## Commits landed this session (chronological)

- `a152360` · Stage 6.4 Playwright DoD spec initial
- `0db9f71` · Fix ordering: navigate before inject
- `1c52219` · Stream-connected banner wait + browser console instrumentation
- `7f7868f` · Bypass BFF routing for spec conversation creation
- `f2d43dd` · Fix agent-server list/create shapes
- `2231245` · Stage 6.4 close-out (DoD met logs)
- `f77cf38` · Q2: gate `ForkFromHereButton` behind `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED`
- `d0f5829` · Log Q1/Q2/Q3 decisions + verification block
- `a12bc6b` · BUILD_LOG: Stage 6.4 verified
- `493149f` · DEBUG_LOG: pre-existing gitDiff.test.tsx regression filed
- `4dc03ce` · Stage 7-C.2-hotfix: gitDiff fixture drift
- `ce15d6b` · Stage 7-C.2-hotfix: AgentPresetCard assertion
- `cc84382` · Stage 7-C.2-hotfix close-out
- (pending this handoff) · Stage 6.4b open: ADR-025 + stage-6 companion doc

## Colossus operational notes (canonical, unchanged this session)

- **BFF launch target:** `bff.main:app_with_sio` (never `bff.main:app`).
- **BFF flag for E2E specs that use debug-inject:** `FORGE_TIMELINE_DEBUG_INJECT=1`.
- **Prod frontend:** `next start -p 3100` (never `next dev`).
- **vLLM :8501 is currently DOWN** — BFF `/api/runs` returns 200 with `status="blocked"` until vLLM is brought up.
- **`pnpm test:unit`** is the correct script name.
- **Next sub-session's first act:** implement `bff/services/worktree.py` per step 1 above.
