# Forge-OH SESSION_HANDOFF

_Last updated: 2026-08-06 06:38 EDT_

## Current stage/plugin/port

- **Stage:** 6.4 — fork-from-here on user messages
- **Status:** DoD MET at all four verification layers
  (BFF pytests, FE Vitest, `pnpm build`, and Playwright E2E).

## Completed this session

- Fixed BFF fork wire-key regression (`from_event_id`) at BFF, FE, and unit-test layers (commit `c0a1e3f` — pre-session).
- Wrote `src/tests/e2e/run-fork-from-here.spec.ts` — Stage 6.4 Playwright DoD spec (302 → 317 lines).
- Iterated 5× on the spec to make it pass on Colossus (see commits `a152360`, `0db9f71`, `1c52219`, `7f7868f`, `f2d43dd`).
- Root-caused BFF Socket.IO handshake 403/404: BFF was being launched with `uvicorn bff.main:app` (bare FastAPI, no socket.io mount). Correct target is `bff.main:app_with_sio`. Logged in DEBUG_LOG 2026-08-06 06:37 EDT.
- Final Playwright run: **1 passed in 1.3s**.

## Remaining before DoD

**None for Stage 6.4 as originally scoped.**
D3 (per-run worktree file revert) was already deferred by decision.

## Open questions awaiting user

1. Close Stage 6.4 as done (D3 deferred to a separate 6.4b slice for isolated per-run worktrees), or hold Stage 6.4 open until 6.4b is scoped?
2. Should `ForkFromHereButton` be gated by `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` like `ForkRunModal`, or stay always-on for user-message events? (Not blocking the DoD — orthogonal to the wire regression fix.)
3. Update the `forge-oh-colossus-ops` skill to codify `bff.main:app_with_sio` as the canonical BFF launch target? (Recommended — prevents this session's dead end from recurring.)

## Exact next action

- **Await user decision on the two open questions above.**
- If user closes Stage 6.4: move to Stage 6.5 per `docs/reconciliation-plan-v1.md`.

## Colossus operational notes (canonical)

- **BFF launch target:** `bff.main:app_with_sio` (never `bff.main:app`).
- **BFF flag for E2E specs that use debug-inject:** `FORGE_TIMELINE_DEBUG_INJECT=1`.
- **Prod frontend:** `next start -p 3100` (never `next dev`; HMR reload races the spec).
- **vLLM :8501 is currently DOWN** — BFF `/api/runs` returns 200 with `status="blocked"` until vLLM is brought up. Stage 6.4 spec bypasses this by talking to agent-server :8090 directly. If future slices need a real live run, launch vLLM via the `forge-oh-llm-serving` recipe.
- **Stale next-server cleanup between runs:**
  ```bash
  pgrep -af 'next-server' | awk '{print $1}' | xargs -r sudo kill -9 2>/dev/null
  fuser -k 3100/tcp 2>/dev/null
  sleep 2
  ```
