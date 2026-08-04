# SESSION_HANDOFF

**Last session:** 2026-08-03 23:47 EDT
**Current branch:** `slice/g1-nightly-harness`

## Current stage / plugin / port

**Stage:** G.1 — on-demand self-eval harness. Post-live-cycle bug fix
chain (5 hotfixes in this session).
**Ports touched:** none. All changes are inside BFF service layer +
harness client-side timeouts + ops scripts.
**ADR-011:** still Proposed. Flip to Accepted after next green live
cycle.
**ADR-012:** Proposed. Refactor BFF `create_run` to async-warmup with
Socket.IO failure events. NOT ratified by this session's fix.

## Completed this session (chronological)

1. `agentPresetId` schema fix in harness + preset resolver.
2. `forge-restart.sh` / `forge-status.sh` service management wrappers.
3. Orphan `next-server` reap via argv-match pattern; PID-via-`/proc`
   descendant walk.
4. `forge-doctor.sh` diagnostic (9 sections, `bash -n` clean) + skill
   auto-load update (`forge-oh-colossus-ops` v2 with runtime triage).
5. Harness `POST /api/runs` timeout raised 30 s → 90 s + regression
   test; ADR-012 stub authored.
6. `bff.main:app_with_sio` entrypoint used everywhere (frontend was
   binding to `bff.main:app` without Socket.IO). Restart scripts fixed.
7. **This commit:** `EventRelay._run_loop` unblocked — sidecar producer
   work moved to `asyncio.to_thread`, per-event `sleep(0)` yield-point
   added. Root cause found via `py-spy dump`. See DEBUG_LOG
   2026-08-03 23:40 EDT.

## Remaining before G.1 Definition of Done is met

Per ADR-011 §DoD:

1. **Deploy the event-loop fix on Colossus and rerun the cycle.** Exact
   commands in "Exact next action" below.
2. **Purge leaked conversation `c07b8803-…`** from agent-server (and
   trajectories DB) so its EventRelay doesn't restart on BFF startup
   and re-hog the loop. Command in "Exact next action".
3. **One green live cycle** — either `tasks_passed > 0` or a
   model-legitimate `tasks_failed > 0`. Any remaining
   `transport error (ReadTimeout)` verdict means the fix is
   incomplete; drop to DEBUG_LOG and take fresh py-spy dumps.
4. **Flip ADR-011 Proposed → Accepted** once (3) is green.
5. **Playwright smoke** for the `/selfeval` UI:
   `cd src && npx playwright test tests/e2e/selfeval.spec.ts`.

## Follow-up slices queued (NOT this slice)

- **Backlog cap:** sidecar_producers should drop-oldest at ~200
  events/conversation to prevent runaway producers.
- **Orphan-relay shutdown:** EventRelay for conversations idle
  > N minutes should self-terminate.
- **Doctor py-spy integration:** if a cycle stalls without new
  `POST /api/runs` log lines, doctor should take a py-spy dump.
- **ADR-012 implementation:** async warmup + Socket.IO failure events.

## Open questions / ambiguity

None currently. All decisions this session were deterministic given
the py-spy evidence.

## Exact next action

**On Colossus, one paste-able block:**

```bash
cd ~/dev/forge-oh
git fetch origin
git checkout slice/g1-nightly-harness
git pull --ff-only

# 1) Purge the leaked c07b8803 conversation on agent-server
CID=c07b8803-aa7a-4059-ae01-523c5e5337b4
curl -s -X DELETE "http://127.0.0.1:8090/api/conversations/${CID}" \
  -w '\nagent-server DELETE HTTP %{http_code}\n'

# 2) Bounce BFF (loads the event-loop-yield fix)
fuser -k 8081/tcp 2>/dev/null; sleep 2
nohup .oh-venv/bin/uvicorn bff.main:app_with_sio \
  --host 127.0.0.1 --port 8081 \
  > .forge-logs/bff.log 2>&1 &
echo $! > .forge-logs/bff.pid
sleep 4
curl -sf http://127.0.0.1:8081/docs -o /dev/null && echo "BFF up (pid $(cat .forge-logs/bff.pid))"

# 3) Confirm no leaked relay by py-spy sampling an idle BFF
sudo /home/rmholston/dev/forge-oh/.oh-venv/bin/py-spy dump \
  --pid $(cat .forge-logs/bff.pid) 2>&1 | head -25
# Expect: MainThread idle, blocked in select/epoll (asyncio idle), NOT
# in build_plan or _rmw.

# 4) Run the new regression tests
cd ~/dev/forge-oh
.oh-venv/bin/pytest bff/tests/test_event_relay_yield.py -v

# 5) Live self-eval cycle
: > .forge-logs/bff.log
systemctl --user restart forge-oh-selfeval.service
sleep 180
cat docs/selfeval/$(date +%Y-%m-%d)-selfeval.json | jq \
  '.tasks_passed, .tasks_failed, .tasks_timed_out, .tasks_errored,
   .outcomes[0].verdict, .outcomes[0].duration_sec,
   .outcomes[0].failure_detail'

# 6) If ANY tasks_passed OR tasks_failed > 0 with a non-transport
# verdict, G.1 is unblocked. Flip ADR-011 to Accepted.
```

## Runtime state at handoff

- BFF `:8081` — running with `bff.main:app_with_sio`, NO `--reload`,
  event-loop-yield fix not yet deployed (waits for next `git pull`).
- Agent-server `:8090` — pid 1483506 (started 22:35 EDT), holds two
  conversations from the 22:58 hung cycle
  (`0b0c5df2-…`, `c8bc917e-…`) plus the leaked `c07b8803-…`.
- Next.js `:3000` — child of `pnpm dev`, currently up.
- vLLM coder `:8501` — DOWN. Not required for G.1 (harness talks to
  BFF, not vLLM; BFF's LLM warmup falls through to Ollama). Ratchet
  back up only if the harness starts producing model-legitimate
  failures we want to interpret against the intended coder.
- vLLM planner `:8511` — DOWN. Same reasoning.
- Ollama `:11434` — UP.
- Workspace UUIDs: `18c99443b23c452899010095abd5f29b` (repo),
  `6dac22aed0e44798b04ea335a405528a` (smoke).

## Log paths reminder

- LIVE: `~/dev/forge-oh/.forge-logs/{bff,agent-server,frontend}.log`
- STALE: `~/.forge-oh/*.log` (do not read; predates the log-target fix)

Doctor script `scripts/forge-doctor.sh` currently reads the stale set
in some sections; that mismatch is documented and queued for the next
slice.
