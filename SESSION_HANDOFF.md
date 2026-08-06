# Session Handoff

**Last update:** 2026-08-06 08:33 EDT
**Current stage/plugin/port:** Stage 6.4c · restart-from-here endpoint (ADR-026 §Decision item 1) · `bff/services/restart.py` (new), `bff/routers/runs.py` (new endpoint), `src/components/timeline/RestartFromHereButton.tsx` (not yet built).

## What was completed this session

- **Stage 6.4c step 1c** (assistant / user-message ledger stamping regression fixes): the four fixup commits landed and 81/81 tests went green — see `BUILD_LOG.md` entry `2026-08-06 04:12 EDT`.
- **Stage 6.4c step 1d — backend COMPLETE** (this commit set, `7bca18e`):
  - `bff/services/restart.py` (new, ~400 lines): `RestartError`, `RestartResult`, `restart_from_here(app, *, source_run_id, anchor_event_id)`.
    - 9-step composition: source-conversation GET → ledger `bulk_get_shas` → anchor event fetch + validate (MessageEvent + source=='user') → source-repo resolve for worktree → mint `run-<hex12>` + `provision_worktree(..., base_ref=anchor_sha)` → POST `/api/conversations` with source's agent config → POST `/events` seed with anchor text (run:true) → best-effort seed-sha ledger stamp → return `RestartResult`.
    - Worktree rollback on both create-failure and seed-failure via `remove_worktree(new_run_id, missing_ok=True)`.
  - `bff/routers/runs.py`: `RestartRunRequest` pydantic (required `from_event_id: str`), `_RESTART_CODE_TO_STATUS` map (404/409/502), `POST /runs/{run_id}/restart` handler with `Request` injection to reach `app.state.event_commit_db`.
  - `bff/tests/test_runs_restart.py` (new, 16 tests, 3 classes) — all green.
  - Regression: `test_runs_sha_capture` (14) + `test_runs_fork` (9) + `test_runs_worktree` (7) + `test_event_commit_ledger` (15) → 68/68 green including new tests. Verified on Colossus 2026-08-06 08:32 EDT.

## What remains before Stage 6.4c Definition of Done

1. **Step 2 (frontend, next session):** `RestartFromHereButton.tsx` timeline component.
   - Visible only on `MessageEvent` events with `source: 'user'`.
   - Gated behind `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` (same flag family as fork-from-here in step 1c).
   - Calls `POST /api/runs/{run_id}/restart` with `{ from_event_id }`, on success navigates the router to `/runs/{restarted_run_id}` (matches fork's post-action nav).
   - Include vitest coverage: renders on user message, hidden on assistant, disabled while pending, error-toast on non-2xx, success-nav on 200.
   - Wire the button into the event inspector alongside the existing "Fork from here" button.
2. **End-to-end Colossus verify script** — extend the pattern from `scripts/stage-6.4b-verify.sh`:
   - Create a run with a two-message conversation (user + assistant reply).
   - POST `/api/runs/{id}/restart` with `from_event_id` of the user message.
   - Assert HTTP 200, new `restarted_run_id`, new `worktree_path` (differs from source), and that the new worktree's HEAD matches the sha captured for the anchor event.
   - Assert failure paths: unknown event id → 404, no-sha ledger row → 409.

## Open questions / ambiguities awaiting user

- **None.** ADR-026 §Storage locked the Option-R2 design; step 1d shipped on that design without deviation.

## Exact next action

Start step 2 (frontend):

```bash
cd ~/dev/forge-oh && git pull --ff-only
```

Then read the existing "Fork from here" button implementation for the pattern:

```bash
grep -rln --include='*.tsx' 'from_event_id\|ForkFromHere\|useForkRun' src/ | head
```

Build `src/components/timeline/RestartFromHereButton.tsx` from that template, add vitest, wire it into the event inspector next to the fork button. Backend is stable at `7bca18e`; frontend can be developed and shipped independently since the endpoint contract is locked.
