# Session Handoff

**Last update:** 2026-08-06 08:41 EDT
**Current stage/plugin/port:** Stage 6.4c · restart-from-here (ADR-026) — backend at `7bca18e`, frontend at `aff6062`. Remaining scope: end-to-end Colossus verify script.

## What was completed this session

- **Stage 6.4c step 1c** (four fixup commits landing user-message ledger stamping tests): 81/81 green — `BUILD_LOG.md` entry `2026-08-06 04:12 EDT`.
- **Stage 6.4c step 1d — backend (`7bca18e`):** `bff/services/restart.py` (new, ~400 lines) + `bff/routers/runs.py` (`RestartRunRequest`, `_RESTART_CODE_TO_STATUS`, `POST /runs/{run_id}/restart`) + 16 tests. 68/68 regression + new green on Colossus.
- **Stage 6.4c step 2 — frontend (`aff6062`, this final commit):**
  - `ENDPOINTS.RUNS.restart(runId)`, `restartRun()` API, `useRestartRun()` hook.
  - `src/components/domain/RestartFromHereButton.tsx` — parallel to `ForkFromHereButton`. Wire key `from_event_id`. Copy explicitly promises "resets files on disk" per ADR-026 §Storage.
  - Mounted next to `ForkFromHereButton` in the event-inspector aside on `src/app/(dashboard)/runs/[runId]/page.tsx` — same visibility gate (`displayEv.type==='message' && source==='user'`), same feature flag (`NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED`).
  - 12 vitest cases green; combined with fork button = 22/22. `pnpm typecheck` clean.

## What remains before Stage 6.4c Definition of Done

**End-to-end Colossus verify script** (`scripts/stage-6.4c-verify.sh`), following the `scripts/stage-6.4b-verify.sh` pattern:

1. Create a source run against real BFF + real agent-server; wait for two events (initial user + first assistant).
2. `GET /api/runs/{source_id}/events` → confirm the user event has a captured `sha` in the ledger response.
3. `POST /api/runs/{source_id}/restart` with `{from_event_id: <user_ev_id>}`.
4. Assert HTTP 200, response has `restarted_run_id`, `worktree_path` distinct from the source's working dir, and `reset_to_sha` == the sha from step 2.
5. Poke the new run's worktree via a lightweight sh-inside-BFF proxy or just `git -C {worktree_path} rev-parse HEAD` — must equal `reset_to_sha`.
6. Negative paths — asserts against a fresh source run: (a) unknown `from_event_id` → 404; (b) `from_event_id` pointing at an assistant event → 409; (c) `from_event_id` pointing at a user event with no ledger row → 409.
7. Best-effort cleanup: `DELETE /api/runs/{restarted_run_id}` + source.

## Open questions / ambiguities awaiting user

- **None** on backend or frontend. On the verify script:
  - Should this be an end-to-end **shell** harness like `stage-6.4b-verify.sh`, or a pytest-under-BFF-venv integration test analogous to `test_runs_restart.py` but hitting real HTTP? Pattern reads shell — will follow that unless corrected.

## Exact next action

Author `scripts/stage-6.4c-verify.sh` following the `stage-6.4b-verify.sh` shape. Before writing, read `stage-6.4b-verify.sh` end-to-end to inherit its idioms (setup, assertion helpers, cleanup trap). Then verify a full green run against the live Colossus BFF + agent-server on `:8081` / `:8090`.

Backend at `7bca18e`, frontend at `aff6062`, close-out log entries appended (see `BUILD_LOG.md`).
