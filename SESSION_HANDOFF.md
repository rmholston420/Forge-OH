# Forge-OH SESSION_HANDOFF

_Last updated: 2026-08-06 08:26 EDT_

## Current stage/plugin/port

- **Stage 6.4 — CLOSED (2026-08-06).** Fork-from-here on user-message events. Non-destructive. Fully verified.
- **Stage 6.4b — CLOSED (2026-08-06 07:31 EDT).** Per-run git worktrees.
- **Stage 6.4c — IN PROGRESS.** Restart-from-here per ADR-026. Steps 1a + 1b + 1c COMPLETE. Step 1d next.

## What was completed this session

**Stage 6.4c step 1c (this slice): runs router capture points + read-path threading**

- `bff/routers/runs.py` — `Request` injected into `create_run`, `send_run_message`, `delete_run`, `get_run_events`. Four capture / cascade blocks wired per ADR-026 §Storage, each wrapped in try/except so ledger failures never break the primary handler path.
- `bff/services/worktree.py` — added `head_sha(worktree_path)` helper (`git rev-parse HEAD` with 40-char hex validation, `None` on any failure).
- `bff/tests/test_runs_sha_capture.py` — new file, 14 tests across 4 classes (create / send-message / delete / get-events). All green after three fixup rounds.
- Regression: 81/81 tests green across `test_runs_sha_capture`, `test_runs_fork`, `test_runs_worktree`, `test_event_commit_ledger`, `test_event_normalize_commit_sha`, `test_event_normalize`.

**Commits pushed this session (in order):**
1. `0143172` — step 1c initial (router + worktree helper + tests).
2. `013be31` — fixup 1: `_FakeUpstream` matcher + wire key (`id` not `event_id`).
3. `1a761fe` — fixup 2: add required `title` to `CreateRunRequest` test bodies.
4. `2dda3d7` — fixup 3: two-tier URL matcher (suffix-first, substring-fallback).
5. (about to push) — BUILD_LOG + SESSION_HANDOFF update.

## What remains before Stage 6.4c Definition of Done

Per ADR-026 §Storage:

- [x] **1a** — `bff/services/event_commit_ledger.py` (aiosqlite, `record_sha` / `bulk_get_shas` / `delete_run`) + 15 tests + `main.py` lifespan wiring.
- [x] **1b** — `bff/services/event_normalize.py` gains `sha_lookup=` kwarg on `normalize_event` + `normalize_events`; stamps `commit_sha_at_time_of_event` on user MessageEvents when the lookup hits. 12 tests.
- [x] **1c** — `bff/routers/runs.py` capture points + read-path threading + cascade delete + `worktree.head_sha` helper. 14 tests.
- [ ] **1d** — `bff/services/restart.py` composition module + `POST /api/runs/{run_id}/restart` endpoint. Provisions fresh worktree checked out at `<sha>` from ledger, seeds it with the user-message text from `from_event_id`, mints new agent-server conversation. Needs 8+ tests: happy path, missing sha, missing event, worktree provision failure, agent-server create failure, non-user-message anchor, source-run-not-found, cross-workspace guard.
- [ ] **2** — Frontend `RestartFromHereButton.tsx` next to existing `ForkFromHereButton` on user-message event cards. Gated behind `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED`. Vitest coverage.
- [ ] **Colossus integration verify** — end-to-end script following the pattern in `scripts/stage-6.4b-verify.sh`: create run → send messages → restart-from-here on a mid-conversation user event → assert new run's working_dir is a different worktree at the anchored sha → assert files match the sha's tree.

## Open questions / ambiguities awaiting user answer

None at present. Design is locked (ADR-026 §Storage W2). Implementation proceeding one step per commit at user's chosen X granularity.

## Exact next action

Step 1d in three commits (backend module + endpoint + tests → one commit; frontend button + vitest → one commit; Colossus integration verify + BUILD_LOG close-out → one commit). Start with:

1. Inspect `bff/services/idempotency_ledger.py` and `bff/services/worktree.py` as reference patterns (already read this session).
2. Write `bff/services/restart.py` with `restart_from_here(app, source_run_id, anchor_event_id) -> {new_run_id, worktree_path, commit_sha, message_text}`. Composition: `event_commit_ledger.bulk_get_shas` for anchor's sha, `worktree.provision_worktree` at that sha, `client.post("/api/conversations", json={...})` with fresh worktree, seed with anchor's `content[0].text` via `client.post("/api/conversations/{new_cid}/events", ...)`. Rollback path: if create fails after worktree provision, remove worktree.
3. Add `POST /api/runs/{run_id}/restart` handler in `bff/routers/runs.py` calling into that module. Request body: `{"from_event_id": str}`.
4. Write `bff/tests/test_runs_restart.py` with the 8 test cases enumerated above.
5. Commit + push + verify on Colossus.

## Reference URLs and file locations (immutable this session)

- Working checkout: `/tmp/forge-oh-work` (kept in sync via `git pull --ff-only`)
- Colossus repo: `~/dev/forge-oh` (host = "Collosus")
- BFF venv: `~/dev/forge-oh/.oh-venv/bin/`
- Ledger schema: `bff/services/event_commit_ledger.py`
- Normalizer with sha_lookup: `bff/services/event_normalize.py`
- Worktree service (+head_sha): `bff/services/worktree.py`
- Router with capture points: `bff/routers/runs.py`
- ADR: `docs/adr/026-restart-from-here.md`
