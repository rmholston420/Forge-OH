# Forge-OH — Session Handoff

**Last updated:** 2026-08-03 10:38 EDT

## Current build-sequencing stage

Slice F (Trajectory Memory, Rec #3). Kernel side of the pipeline is
end-to-end wired AND signal fields are populated.

## What was completed this session

- **F.12** — sidecar producer for `task_description` (seeded at
  conversation-create in `bff/routers/runs.py`).
- **F.13** — background drain scheduler in the BFF lifespan +
  `POST /api/trajectories/drain` endpoint.
- **F.14** — fixed `final_status` attribution in the STOP hook.
  Introduces `_infer_final_status`: sidecar-override > verify verdict
  > STOP-hook default (SUCCESS) > UNKNOWN (unrecognized verdict only).
- **F.15** — sidecar producers for `plan`, `diffs`, `symptom`, and
  `repograph_symbols`. Wired into `event_relay._run_loop`; each
  event is fed through `bff/services/sidecar_producers.update_from_event`.
  Per-conversation accumulator, bounded to 5000 events, reset on
  terminal status.

**Test totals:** 434 passing offline-safe backend (baseline 387;
+47 across F.12/F.13/F.14/F.15). 0 regressions. 14 pre-existing
localhost-only failures unchanged (`test_mcp_router`,
`test_observability_router`, `test_plugins_router`). Ruff clean.

## What remains before the current DoD is met

Slice F kernel work is done. Full-loop live verification on
Colossus needs a fresh run to confirm all four fields populate.

1. Pull latest on Colossus (`~/dev/forge-oh/`) and restart the BFF
   so both the drain scheduler AND the new event-tap are live.
2. Fire one run via curl (or the UI) with a real prompt.
3. After the agent finishes (natural `finish` call → STOP hook
   fires), force-drain and inspect the sidecar + DB row.

## Open questions / ambiguities awaiting your answer

None currently.

## Deferred items (non-blocking)

- Retention policy ADR for `trajectories.db`.
- Backfill: attribute the two pre-F.12 orphan rows (task_description
  empty).
- If any F.15 producer proves noisy in practice (e.g. RepoGraph
  action `kind` naming drifts), the map at the top of
  `sidecar_producers.py` is the single place to adjust.
- Fresh recommendation outside Rec 1/2/3.

## Exact next action to take

On Colossus:

```bash
cd ~/dev/forge-oh
git pull --ff-only
pkill -9 -f 'uvicorn bff.main:app' || true
scripts/forge-up.sh

# Fire a fresh live run via curl:
RESP=$(curl -s -X POST http://127.0.0.1:8081/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"title":"F.14 F.15 verify","agentPresetId":"ap-1","workspaceId":"18c99443b23c452899010095abd5f29b","taskPrompt":"write a python one-liner that prints hello world"}')
CID=$(echo "$RESP" | jq -r '.data.id')
echo "conversation: $CID"

# Watch the sidecar populate in real time
watch -n 2 "cat /home/rmholston/dev/forge-oh/.forge-oh/trajectory-sidecar.json | jq ."

# When done (agent finishes on its own), force drain + check DB:
curl -s -X POST http://127.0.0.1:8081/api/trajectories/drain | jq
sqlite3 ~/.forge-oh/trajectories.db \
  "SELECT substr(run_id,1,8), task_description, final_status,
          length(diffs_json), length(plan), symptom,
          length(embedding)
   FROM trajectories ORDER BY created_at DESC LIMIT 3;"
```

Slice F DoD met when the newest row has:

- non-empty `task_description`
- `final_status` = `success` (not `unknown`)
- non-null `embedding` (`length(embedding) > 0`)
- best-effort populated `plan` / `diffs_json` / `symptom` when those
  signals were emitted by the run
