# Forge-OH Session Handoff

**Current stage:** Slice F (Trajectory Memory, Rec #3) shipped at
`v1.0-alpha3`. Follow-up quality gates F.10 (topology fix) and F.11
(live E2E) both landed on `main`.

## Last commits

- `6c290da` — F.10: agent-server topology change (docker → .oh-venv +
  `FORGE_OH_TRAJECTORY_DB` env pin so BFF, hook, and agent all share a
  single SQLite path).
- `e2e7350` — F.9: `hook_config` injected into the create body of
  `POST /api/conversations`; `.openhands/hooks.json` published as the
  canonical workspace config; 10 new unit tests for `build_hook_config()`.
- `de8c837` — F.8: ADR-008 (Trajectory Memory) + first E2E for the
  Trajectory Memory panel; tag `v1.0-alpha3`.

## Verified this session

- Agent-server runs in `.oh-venv` (no docker container). Pidfile at
  `.forge-logs/agent-server.pid`, log at `.forge-logs/agent-server.log`.
- Smoke-tested `openhands_tools_ext.trajectory.hook` end-to-end against
  a synthetic `Stop` HookEvent — wrote and read back
  `traj_smoke-test-1` in `~/.forge-oh/trajectories.db`. Row deleted
  after verification.
- Both STOP hooks fire only when `execution_status == FINISHED` — i.e.
  the agent naturally reached a `finish` tool call. Interrupt-driven
  stops do NOT fire hooks (confirmed against the SDK source).

## Next up

**Immediate:**
1. Run the new live E2E on Colossus after a fresh `git pull`:
   ```
   LIVE_HOOKS_E2E=1 npx playwright test src/tests/e2e/hooks-live.spec.ts
   ```
   This creates a real run, waits for it to finish, and asserts both
   STOP hooks wrote their expected artifacts. Reports pass/fail
   without any manual UI interaction. Skips cleanly without the env
   gate so it is safe in CI.
2. If the run times out at 4 minutes, bump
   `LIVE_HOOKS_E2E_TIMEOUT_MS`. If the trajectory row is missing but
   the run succeeded, check `.forge-logs/agent-server.log` for hook
   stderr — that's the most likely failure mode.

**Deferred (non-blocking, listed in priority order):**
1. Sidecar producer for `.forge-oh/trajectory-sidecar.json` — trajectory
   hook degrades gracefully today but populates fewer fields (empty
   `plan`, `symptom`, `repograph_symbols`, `diffs`).
2. Indexer drain schedule (background embedding for records inserted
   without `FORGE_OH_TRAJECTORY_INDEX_INLINE=1`).
3. Retention policy ADR for `trajectories.db`.
4. Fresh recommendation outside Rec 1/2/3.

## Open questions

None outstanding.

## Repo state

- Mirror: `/home/user/workspace/forge-oh-mirror/` on `main`, uncommitted
  F.11 changes (new spec + this handoff + BUILD_LOG entry) about to be
  committed and pushed as part of this turn.
- Colossus: `~/dev/forge-oh/` on `main` at `6c290da` — needs to pull
  F.11 before running the new live spec.

## Test totals

- Backend offline-safe: **270 passed** (14 pre-existing localhost-only
  failures unchanged).
- Frontend unit: 838 passed (1 pre-existing jsdom Blob flake in
  `lib-api-client.test.ts` — leave alone).
- E2E: 3 specs — `repograph-panel.spec.ts`,
  `trajectory-memory-panel.spec.ts`, and now
  `hooks-live.spec.ts` (skip-guarded).
