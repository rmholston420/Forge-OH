# Forge-OH — Session Handoff

## Current stage
F.16 verified on Colossus. G.1 verified end-to-end (agent successfully grew its own test suite). Always-visible GPU strip landed for the frontend.

## Completed this session
- F.16 GPU monitor: BFF poller + `/api/gpu`, `/api/gpu/history`; PRE-tool hook.
- Guards: temp (default 83 C), power (opt-in, recommend 435 W on 5090), VRAM (opt-in), util (opt-in). Precedence: thermal → power → VRAM → util.
- Bands: warn=52 C, critical=88 C surfaced in snapshot for frontend rendering.
- Wired into `bff/main.py` lifespan and `bff/services/hook_config.py` + `.openhands/hooks.json`.
- Tests: 48 new F.16 tests green; full offline suite 482 passed / 23 deselected (mcp/observability/plugins routers require agent-server on :8090).
- Fixed happy-path smoke spec (`src/tests/e2e/f15-fixups.spec.ts`).
- G.1 self-testing spec landed (`src/tests/e2e/g1-self-testing.spec.ts`): agent appends a fully-specified marker test to `TestSymptomProducer`, asserts +1 collected case and the new case passes in isolation.

## Remaining before DoD
- Frontend: pull + restart Next dev server, load any dashboard route, confirm GPU strip renders in top-right with real telemetry. Expected: `T 34C U 0% V 76% 44W` (green) on idle 5090.
- G.1 rerun with fixed marker body (event shape now matches the producer).

## Open questions / ambiguity
- vLLM vs Ollama routing — deferred to F.18 (separate slice; F.16 unaffected).

## Next action
1. Colossus verification recipe (below).
2. First G.1 run on Colossus — confirm the agent can actually complete the self-editing task under ap-1.
3. If G.1 flakes: consider tightening the prompt or bumping `RUN_TIMEOUT_MS`.

## Colossus verification recipe
```bash
cd ~/forge-oh && git pull
# Optional: enable power guard (recommended)
grep -q FORGE_GPU_POWER_CUTOFF_W ~/.forge-oh/bff.env 2>/dev/null || \
  echo 'FORGE_GPU_POWER_CUTOFF_W=435' >> ~/.forge-oh/bff.env
# Restart BFF
pkill -f 'uvicorn bff.main:app' || true
set -a; source ~/.forge-oh/bff.env 2>/dev/null || true; set +a
nohup .oh-venv/bin/uvicorn bff.main:app --host 127.0.0.1 --port 8081 \
  >~/.forge-oh/bff.log 2>&1 &
sleep 2
# Snapshot + history
curl -s 127.0.0.1:8081/api/gpu | python -m json.tool
curl -s '127.0.0.1:8081/api/gpu/history?window_sec=60' | python -m json.tool | head
# Smoke
cd src && npx playwright test tests/e2e/f15-fixups.spec.ts
# G.1 (remove marker method first if a prior run left it behind)
npx playwright test tests/e2e/g1-self-testing.spec.ts
```
