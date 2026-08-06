# Forge-OH SESSION_HANDOFF

_Last updated: 2026-08-06 06:42 EDT_

## Current stage/plugin/port

- **Stage 6.4 — CLOSED.** DoD met at all four verification layers.
- **Next stage to start:** whatever comes next in
  `docs/reconciliation-plan-v1.md` after 6.4. (User to confirm which,
  and whether Stage 6.4b — per-run worktrees + D3 file revert — should
  be scheduled before or after that.)

## Completed this session

- BFF fork wire-key regression fix (pre-session, commit `c0a1e3f`) — 38/38 regression, 9/9 fork pytests, 9/9 Vitest, clean `pnpm build`.
- Stage 6.4 Playwright DoD spec `src/tests/e2e/run-fork-from-here.spec.ts` — passing 1/1 in 1.3s on Colossus.
- Root-caused BFF Socket.IO 403/404 to launching `uvicorn bff.main:app` (bare FastAPI, no Socket.IO mount) instead of `bff.main:app_with_sio`. Logged in DEBUG_LOG 2026-08-06 06:37 EDT.
- **Q1:** Stage 6.4 closed; Stage 6.4b to be opened separately for per-run worktrees + D3.
- **Q2:** `ForkFromHereButton` gated behind `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` symmetric with `ForkRunModal`. New Vitest case added.
- **Q3:** `forge-oh-colossus-ops` skill updated (corrected BFF module line + new Socket.IO-handshake triage entry).

## Verification pending on Colossus (single paste-able block)

```bash
cd ~/dev/forge-oh
git pull origin main

# 1) Vitest: the button suite should now be 10/10 (was 9/9).
#    Script name is `test:unit` (NOT test:vitest — that name doesn't exist in package.json).
pnpm test:unit -- src/tests/unit/domain-ForkFromHereButton.test.tsx 2>&1 | tail -20

# 2) Clean prod build.
pnpm build 2>&1 | tail -8

# 3) Re-run the Playwright DoD spec (BFF must be on app_with_sio; already the case
#    from this session's restart on :8081 with FORGE_TIMELINE_DEBUG_INJECT=1).
pgrep -af 'next-server' | awk '{print $1}' | xargs -r sudo kill -9 2>/dev/null
fuser -k 3100/tcp 2>/dev/null
sleep 2
FORGE_TEST_WORKING_DIR=/home/rmholston/dev/forge-oh \
PLAYWRIGHT_START_PROD=1 \
PLAYWRIGHT_BFF_URL=http://127.0.0.1:8081 \
PLAYWRIGHT_AGENT_URL=http://127.0.0.1:8090 \
PLAYWRIGHT_PROD_PORT=3100 \
  pnpm exec playwright test src/tests/e2e/run-fork-from-here.spec.ts --reporter=list 2>&1 | tail -20
```

Expected: Vitest = 10 passed for the fork-from-here suite (+ everything else green), `pnpm build` clean, Playwright still 1/1.

## Open questions awaiting user

**None blocking.** All three questions from the previous handoff have been decided per the "make the optimal choice" directive and are now landed on `main` (commits `2231245`, `f77cf38`) plus the `forge-oh-colossus-ops` skill update.

- If Stage 6.4b (per-run worktrees + D3 file revert) should be next, confirm and I'll open it against `docs/reconciliation-plan-v1.md` §6.4b.
- Otherwise, name the next stage from the reconciliation plan and I'll restate scope and start.

## Colossus operational notes (canonical)

- **BFF launch target:** `bff.main:app_with_sio` (never `bff.main:app`). Skill `forge-oh-colossus-ops` now has a dedicated Runtime Triage entry for this failure mode.
- **BFF flag for E2E specs that use debug-inject:** `FORGE_TIMELINE_DEBUG_INJECT=1`.
- **Prod frontend:** `next start -p 3100` (never `next dev`).
- **vLLM :8501 is currently DOWN** — BFF `/api/runs` returns 200 with `status="blocked"` until vLLM is brought up. The Stage 6.4 spec bypasses this by talking to agent-server :8090 directly.
- **Between spec runs:**
  ```bash
  pgrep -af 'next-server' | awk '{print $1}' | xargs -r sudo kill -9 2>/dev/null
  fuser -k 3100/tcp 2>/dev/null
  sleep 2
  ```

## Commits landed this session

- `a152360` — Stage 6.4 Playwright DoD spec — initial
- `0db9f71` — Fix ordering: navigate before inject
- `1c52219` — Stream-connected banner wait + browser console instrumentation
- `7f7868f` — Bypass BFF routing for spec conversation creation
- `f2d43dd` — Fix agent-server list/create shapes (`/api/conversations/search` + `workspace: LocalWorkspace`)
- `2231245` — Close-out: BUILD_LOG + DEBUG_LOG + SESSION_HANDOFF (DoD met)
- `f77cf38` — Gate `ForkFromHereButton` behind `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` (Q2)
- `forge-oh-colossus-ops` skill updated in-place (Q3, no commit — skill lives outside repo)
