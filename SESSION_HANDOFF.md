# Forge-OH — Session Handoff

**Last updated:** 2026-08-03 10:00 EDT

## Current build-sequencing stage

Slice F (Trajectory Memory, Rec #3). Kernel side of the pipeline is
end-to-end wired.

## What was completed this session

- **F.12** — trajectory sidecar producer (`bff/services/sidecar.py`,
  wired in `bff/routers/runs.py`). BFF now seeds
  `$WORKSPACE/.forge-oh/trajectory-sidecar.json` at conversation
  create with `session_id` + `task_description`. Trajectory STOP hook
  reads this and produces rows with the real user prompt instead of
  an empty string. 19 unit tests + 2 router tests.
- **F.13** — trajectory drain scheduler
  (`bff/services/trajectory_drain.py`, wired into `bff/main.py`
  lifespan). Background async task calls
  `TrajectoryIndexer.index_pending()` every 60 s (configurable via
  `FORGE_OH_TRAJECTORY_DRAIN_INTERVAL` / `FORGE_OH_TRAJECTORY_DRAIN_BATCH`).
  `POST /api/trajectories/drain` forces an immediate pass and
  returns metrics. 19 unit tests + 3 endpoint tests.

**Test totals:** 409 passing offline-safe backend (baseline 387;
+22 new). 0 regressions. 14 pre-existing localhost-only failures
unchanged (`test_mcp_router`, `test_observability_router`,
`test_plugins_router`). Ruff clean.

## What remains before the current DoD is met

Slice F kernel work is done. Full-loop E2E confirmation on Colossus
still needed:

1. Pull latest on Colossus (`~/dev/forge-oh/`) and restart the BFF
   so the drain scheduler is running.
2. Re-run `scripts/forge-up.sh` and issue a live run through the
   agent-server.
3. After the run finishes, confirm the row in
   `~/.forge-oh/trajectories.db` has (a) a non-empty
   `task_description` and (b) a non-null `embedding` blob (via
   `POST /api/trajectories/drain` for an immediate pass, or wait
   60 s).
4. Then re-run the live E2E (`LIVE_HOOKS_E2E=1 pnpm playwright test`
   in `frontend/`).

## Open questions / ambiguities awaiting your answer

None currently.

## Deferred items (non-blocking)

- Fix verify hook so it actually writes `verify-state.json`
  (workspaces/*/.forge-oh/ empty on live runs — trajectory rows still
  work because trajectory hook doesn't depend on verify state).
- Retention policy ADR for `trajectories.db`.
- Additional sidecar producers (planner, verify symptom, repograph
  symbols, diffs) — can layer on top using
  `sidecar.update_sidecar()`.
- Fresh recommendation outside Rec 1/2/3.

## Exact next action to take

Pull on Colossus and run the live E2E:

```bash
cd ~/dev/forge-oh
git pull --ff-only
# restart BFF so the F.13 drain scheduler picks up on lifespan startup
pkill -f 'uvicorn bff.main:app' || true
scripts/forge-up.sh
# in another terminal, once BFF healthy:
cd ~/dev/forge-oh/frontend
LIVE_HOOKS_E2E=1 pnpm playwright test
```

After the run completes, force an immediate embed and inspect the DB:

```bash
curl -s -X POST http://127.0.0.1:8000/api/trajectories/drain | jq
sqlite3 ~/.forge-oh/trajectories.db \
  "SELECT run_id, task_description, length(embedding) FROM trajectories ORDER BY started_at DESC LIMIT 3;"
```

Both `task_description` non-empty AND `length(embedding) > 0` is the
Slice F Definition of Done.
