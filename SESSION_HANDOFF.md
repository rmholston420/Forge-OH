# Forge-OH — SESSION_HANDOFF

**Overwrite each session end.** Reflects CURRENT state only. Not append-only.

Last updated: **2026-08-06 09:40 EDT**

---

## Current stage/plugin/port

- **Stage 6.4c — CLOSED.** P1 Restart-from-here shipped end-to-end.
  - ADR-026 **Ratified** with amendment block (2026-08-06 09:29 EDT `toDisplayEvent` projection fix).
  - Backend + frontend + Playwright e2e + `stage-6.4c-verify.sh` all green on Colossus @ `0c01b6e`.
- **Repo hygiene** — 15 stale branches pruned on origin (see below).
- **Next stage per `docs/reconciliation-plan-stage-6.md`**: **Stage 6.5 Runtime model switching** — SDK gap check 6.5.1 first (may defer entire stage if agent-server REST surface is absent).

## What was completed this session (2026-08-06)

### Stage 6.4c closure (single-slice per ADR-026 lock-in)

- Committed as `9eb10ce` → amended to `0c01b6e` after Playwright caught a `toDisplayEvent` projection drop.
- `RestartFromHereButton.tsx` — rules-of-hooks fix, sha-presence gate, ADR-026 §Frontend contract copy verbatim.
- `page.tsx::toDisplayEvent` — `commit_sha_at_time_of_event` added to `DisplayEvent` type and passed through via conditional spread; call site simplified to `commitShaAtTimeOfEvent={displayEv.commit_sha_at_time_of_event ?? null}`.
- `bff/routers/debug.py` — E2E affordance: `raw.pop("commit_sha_at_time_of_event")` builds stub `sha_lookup` so synthetic events can be sha-eligible without ledger touch.
- `src/tests/e2e/run-restart-from-here.spec.ts` — new spec: positive user+sha, negative agent, negative user-no-sha, wire-body assertion, dialog-copy screenshot.
- `docs/adr/026-restart-from-here.md` — Proposed → Ratified with amendment block.

### Colossus verify results

- **pytest**: 56/56 green (`test_debug_inject_endpoint.py` 11/11 · `test_runs_restart.py` 27/27 · `test_runs_sha_capture.py` 18/18).
- **vitest**: 14/14 green (`domain-RestartFromHereButton.test.tsx`).
- **Playwright**: 1/1 green (`run-restart-from-here.spec.ts` 1.9s).
- **`stage-6.4c-verify.sh`**: PASSED — anchor sha `0c01b6e...`, worktree HEAD match, neg A 404, neg C 404.

### Repo hygiene (commit `603b894`, pushed)

- **Rescued 598 lines of unmerged design work** from `audit/frontend-backend-parity` onto main:
  - `docs/adr/010-frontend-parity-scope.md` (Proposed) — F.20–F.31 scope decisions Q1/Q2/Q3.
  - `docs/decisions/2026-08-03-frontend-parity-plan.md` — 12-slice execution plan.
  - `docs/frontend-backend-gap.md` — parity audit (12 gaps identified).
  - `docs/kosmos-plugin-analysis.md` — Kosmos plugin conversion analysis (verdict: NOT NOW; revisit at Phase 5).
  - `docs/adr/README.md` — ADR-010 added as Proposed; stale "historical skip" note removed.
- **Archive tags pushed** (defense-in-depth before delete):
  - `archive/slice-stage1-reconciliation-v1-20260806` → `5b76c98`
  - `archive/slice-dual-mode-routing-adr-20260806` → `8c47975`
  - `archive/audit-frontend-backend-parity-20260806` → `9058ff6`
  - `archive/slice-coder-planner-rebench-20260806` → `d36ed4c`
- **Branches deleted on origin (15 total)**:
  - `slice/stage1-reconciliation-v1` (squashed as #5 · StatusBadge-only unique adds)
  - `slice/dual-mode-routing-adr` (squashed as #6 · StatusBadge-only unique adds)
  - `audit/frontend-backend-parity` (unique docs rescued · remaining files are deprecated stubs)
  - `slice/coder-planner-rebench` (52 commits · all outputs already on main: ADR-013 amendments, ADR-015/016/017, `bench/pathF_swebench/`, F.3 full-500 26.6%/28.6%)
  - 11 `agent/screenshots-*` autobranches (Playwright artifacts; screenshots on main via `git add -f`)

### Origin state after cleanup

- **Branches**: `main` only.
- **HEAD**: `603b894` (`docs: rescue ADR-010 + parity audit + Kosmos plugin analysis`).
- **Prior**: `0c01b6e` (Stage 6.4c CLOSED · closure amend).
- **Archive tags**: 4 tags recoverable via `git checkout archive/<name>` or `git branch resurrect-me archive/<name>`.

## What remains before DoD is met

Stage 6.4c DoD is **CLOSED**. No remaining work on this stage.

## Open questions / ambiguity

**None.**

## Next exact action

**Start Stage 6.5 — SDK gap check first (§6.5.1).** Per reconciliation-plan-stage-6.md, this stage may be deferred entirely if agent-server does not expose runtime model switching over REST. Do NOT fabricate a frontend control against a nonexistent endpoint.

```bash
# 6.5.1 gap check — inspect pinned OpenHands SDK for a runtime-model-switch REST route
# (Read only; no code changes.  Outcome dictates whether 6.5.2-6.5.5 proceed.)
```

If the SDK exposes the route → proceed with 6.5.2 backend forwarding endpoint. If absent → log deferral to BUILD_LOG.md and skip Stage 6.5, move to Stage 6.6 (Skills/Microagents management page).

## Follow-up (out of scope for this slice, deferred)

- `ForkFromHereButton.tsx` shares the same rules-of-hooks bug pattern (`useCallback` after early return). Fix in a separate slice.
- F.20 dead-stub cleanup (delete `bff/routers/agents.py` and `src/app/(dashboard)/settings/secrets/page.tsx`) — scheduled in the rescued `docs/decisions/2026-08-03-frontend-parity-plan.md` under F.20.
- ADR-010 is Proposed — must ratify before any F.20-series slice executes.
