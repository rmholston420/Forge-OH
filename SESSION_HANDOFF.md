# SESSION_HANDOFF

**Last session:** 2026-08-03 22:35 EDT
**Current branch:** `slice/g1-nightly-harness` (module named `selfeval`)
**Branches pushed to origin this session:** `slice/g1-nightly-harness` (pending push of this commit)

## Current stage / plugin / port

**Stage:** G.1 — on-demand self-eval harness. Post-live-cycle bug fix.
**Ports touched:** none. Composes with verify + trajectory + hook + model_router.
**ADR:** ADR-011 (still Proposed — flip to Accepted after next green live cycle).

## Completed this session

- Diagnosed the 422 on Colossus: harness POST /api/runs was missing the
  required field `agentPresetId` (schema: `bff/routers/runs.py:73`).
- Added `_resolve_default_preset_id` (harness.py) + `--preset-id` flag /
  `FORGE_SELFEVAL_PRESET_ID` env (cli.py). Tests updated to pass an
  explicit id and bypass the resolve path. 55/55 still green.
- Added `scripts/forge-restart.sh` — full bounce, `--bff-only`, `--status`.
- Added `scripts/forge-status.sh` — port + pidfile + PID-match snapshot.
- Both scripts wrap existing `forge-up.sh` / `forge-down.sh`. **No systemd
  parallel control path introduced.** vLLM containers deliberately out of
  scope.
- BUILD_LOG entry appended (2026-08-03 22:35 EDT).

## Remaining before G.1 Definition of Done is met

Per ADR-011 §DoD:

1. **Re-run live cycle on Colossus** with the agentPresetId fix:
   ```bash
   cd ~/dev/forge-oh
   git fetch origin && git pull --ff-only origin slice/g1-nightly-harness
   bash scripts/forge-restart.sh --status
   systemctl --user start forge-oh-selfeval.service
   journalctl --user -u forge-oh-selfeval.service -f
   ```
   Expected: at least one task reaches `passed` verdict; `docs/selfeval/*.json`
   contains real BFF run ids; `docs/proposals/*.md` for any non-passing
   tasks.

2. **Kill stale Next.js dev server** (from previous session, PID reported
   as 3657091 on :3000). `forge-restart.sh` handles this automatically now
   — the down step port-kills any lingering listener.

3. **Sidebar "Self-Eval" entry visibility:** load `/selfeval` after the
   restart above. `.next` cache should have been invalidated by the
   restart; if not, `rm -rf .next && bash scripts/forge-restart.sh`.

4. **Playwright smoke:** run with the correct invocation
   `npx playwright test src/tests/e2e/selfeval.spec.ts` (not `npm run
   test:e2e -- ...`).

5. **Flip ADR-011 status Proposed → Accepted** once live cycle is green.

## Open questions / ambiguity

None. `agentPresetId` fix is deterministic against the seed data in
`bff/routers/agent_presets.py` (preset `ap-1` is `isDefault=true`).

## Exact next action

**On Colossus:**

```bash
cd ~/dev/forge-oh
git fetch origin
git checkout slice/g1-nightly-harness
git pull --ff-only
bash scripts/forge-restart.sh --status
# Then trigger a cycle:
systemctl --user start forge-oh-selfeval.service
journalctl --user -u forge-oh-selfeval.service -f
# Inspect:
cat docs/selfeval/$(date +%Y-%m-%d)-selfeval.json | jq '.tasks_passed, .tasks_failed, .tasks_error'
ls docs/proposals/$(date +%Y-%m-%d)-*.md 2>/dev/null || echo "no proposals (all passed?)"
```

## Runtime state at handoff

From previous session's Colossus paste (2026-08-03 22:15 EDT):
- BFF up on :8081, accepting connections.
- Coder vLLM :8501 — presumed up (last known good).
- Planner vLLM :8511 — DOWN (expected during that session's proposer call;
  will auto-swap on next planner request).
- Ollama :11434 up.
- Next.js :3000 held by stale PID 3657091 — will be reaped by
  `forge-restart.sh`.
- Workspace UUIDs: forge-oh-repo=`18c99443b23c452899010095abd5f29b`,
  forge-oh-smoke=`6dac22aed0e44798b04ea335a405528a`.
