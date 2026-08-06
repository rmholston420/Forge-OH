# Forge-OH — SESSION_HANDOFF

_Overwritten each session end. Reflects current state only._

**Timestamp:** 2026-08-06 06:07 EDT

## Current build-sequencing stage / plugin / port

- **Stage:** `docs/reconciliation-plan-stage-6.md` §6.4 — checkpoint-to-disk revert.
- **Scope actually shipped (pared from spec, see BUILD_LOG 2026-08-06 06:07 EDT for full rationale):**
  - Conversation-state revert via SDK-native `from_event_id` fork.
  - File-tree revert DEFERRED — agent-server has no write git routes and the workspace `working_dir` IS the live host repo, so a naïve `git reset --hard` would destroy uncommitted work.

## What was completed this session

- BFF: widened `POST /runs/{run_id}/fork` to accept `{from_event_id?}`. Forwarding uses the exact wire key `from_event_id` (regression-tested — see below).
- Frontend: widened `forkRun`, `ForkAck`, `useForkRun` (back-compat preserved for `ForkRunModal`).
- Frontend: new `ForkFromHereButton` component wired into the event-inspector aside on the run-detail page. Only visible for events where `type=='message' && source=='user'`.
- Frontend: on success, navigates to `/runs/${forked_id}`.
- BFF tests: `bff/tests/test_runs_fork.py` — 9 tests, ALL PASS locally in the sandbox interpreter (`PYTHONPATH=. python3 -m pytest bff/tests/test_runs_fork.py`).
- Frontend tests: `src/tests/unit/domain-ForkFromHereButton.test.tsx` — 9 tests written; not yet run (no Node in sandbox).
- BUILD_LOG entry appended at `2026-08-06 06:07 EDT`.

## What remains before Stage 6.4 DoD is met

**On Colossus (the user must run these):**

```bash
cd ~/dev/forge-oh
source .venv/bin/activate

# 1) BFF fork tests (should be 9/9 pass)
PYTHONPATH=. pytest bff/tests/test_runs_fork.py -v

# 2) Full BFF regression sanity (should still be 36/36 from Stage 6.3 + 9 new = 45+)
PYTHONPATH=. pytest bff/tests/test_runs_fork.py bff/tests/test_idempotency_ledger.py bff/tests/test_idempotency_endpoints.py -v

# 3) Frontend unit test (9 new Vitest cases)
pnpm vitest run src/tests/unit/domain-ForkFromHereButton.test.tsx

# 4) Manual UI click-through — the definition of done for this slice:
#    a. Rebuild Next.js: pnpm build && pnpm start (port 3100)
#    b. Restart BFF: pkill -f 'uvicorn bff.main' ; PYTHONPATH=. uvicorn bff.main:app --host 0.0.0.0 --port 8081 &
#    c. Open http://localhost:3100/runs/<any-existing-runId>
#    d. Send at least two user messages so there are multiple user-message events.
#    e. Click a user-message event in the timeline → inspector aside should show a "Fork from here" button.
#    f. Click it → confirm dialog → "Fork from here" → should navigate to /runs/<new-id> with truncated history.
#    g. Confirm the ORIGINAL run still exists intact when navigating back.
```

**Stop condition:** step 4f above succeeds AND the new run's event list ends at the selected user message.

## Open questions / ambiguities awaiting the user's answer

- **File-tree revert scope**: shipping without it (D3) means "fork from here" only reverts conversation state, not disk. Confirm this is acceptable for Stage 6.4 or whether we open a Stage 6.4b for isolated per-run worktrees before moving on.
- **Feature-flag guard**: `ForkRunModal` uses `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED`. Should the fork-from-here button be gated by the same flag or ship unconditionally? Current implementation ships unconditionally.

## Exact next action to take

1. On Colossus, run the four verification steps above.
2. If any step fails, append a DEBUG_LOG entry with the symptom, and reply here with the exact error text — do not "fix and retry" blind, the wire-key trap is exactly the class of bug that hides behind a green build.
3. If all four pass, reply "6.4 DoD PASS" and I will:
   - Close Stage 6.4 in BUILD_LOG.
   - Open Stage 6.5 (runtime model switching) — expect another spec-vs-reality divergence to investigate; the probe showed `supports_runtime_model_switch: false` on the current conversation.
