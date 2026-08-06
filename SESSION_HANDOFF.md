# SESSION HANDOFF — 2026-08-06 10:22 EDT

## Current build-sequencing stage / plugin / port

**Stage 6.5 · Runtime model switching**

- §6.5.1 CLOSED (verdict PRESENT-as-REST, ADR-027 Ratified)
- §6.5.2 CLOSED (BFF endpoint `POST /runs/{run_id}/model` shipped, 32/32 tests green on Colossus at `f58f66c`)
- **§6.5.3 CODE LANDED — awaiting Colossus verify**

## What was completed this session

1. §6.5.3 UI slice implemented in `/tmp/forge-oh-work`:
   - `RunModelSwitchModal.tsx` — preset picker + Confirm/Cancel, ADR-027 error-contract mapping (200 / 404 / 422 / 503 / 502 → distinct Banner messages).
   - `useSwitchRunModel()` mutation hook mirroring `useRestartRun`.
   - `switchRunModel()` API function + `ENDPOINTS.RUNS.model(runId)`.
   - `RunDetailHeader.tsx` — `🔀 Switch model` button rendered only when `isRunning || isPaused` AND `onSwitchModel` prop is provided.
   - `runs/[runId]/page.tsx` — modal mounted + `modelSwitchOpen` state wired.
   - Vitest: 6 cases (title/preselect, no-op disabled, cancel, 200, 422, 503, 404) via MSW.
   - Playwright e2e: 2 cases (button visible on eligible run + modal open/cancel), skips cleanly when no running/paused run exists.
2. BUILD_LOG entry appended with full slice ledger.

## What remains before §6.5.3 DoD is met

1. **Push to origin/main** (this session).
2. **Colossus verify** — pull, install (should be no-op), run Vitest + production-build Playwright:
   ```bash
   cd ~/dev/forge-oh
   git pull
   npm ci
   npx vitest run src/tests/unit/domain-RunModelSwitchModal.test.tsx
   bash scripts/forge-restart.sh
   fuser -k 3100/tcp 2>/dev/null; sleep 2
   npm run build 2>&1 | tail -8
   NEXT_PUBLIC_BFF_URL=http://127.0.0.1:8081 \
     nohup npx next start -H 127.0.0.1 -p 3100 >~/.forge-oh/next-prod.log 2>&1 &
   sleep 6
   curl -sf http://127.0.0.1:3100/runs >/dev/null && echo OK
   cd src
   PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
     npx playwright test tests/e2e/run-model-switch.spec.ts --reporter=list
   ```
3. If Playwright green → §6.5.3 CLOSED. Update SESSION_HANDOFF to point at §6.5.4 (BUILD_LOG entry timestamped with real Colossus verify time).

## Open questions / ambiguities awaiting user answer

None blocking. One known follow-up filed inline in `page.tsx`: `RunSummary` doesn't expose `agentPresetId`, only `agentPresetName`. Wiring the current preset ID cleanly requires a separate micro-slice (add `agentPresetId` to `RunSummarySchema` + BFF row). Fallback (preset[0] preselection) is functional; user always confirms via the modal's Switch button.

## Commit stack on origin/main (pending push of §6.5.3)

Local stack (sandbox `/tmp/forge-oh-work`, not yet pushed):

- **PENDING** — `Stage 6.5.3: RunModelSwitchModal + header button (ADR-027)` — this session's slice

Already on origin:

- `3037569` SESSION_HANDOFF: Stage 6.5.2 CLOSED + §6.5.3 spec supersession noted
- `f58f66c` Stage 6.5.2: POST /runs/{run_id}/model (ADR-027) with 14 pytest cases
- `0242347` ADR-012 §3 micro-slice: MODEL_ROUTER_CATALOG + compatibility oracle
- `936b5e7` ADR-027 Ratified: switch_llm-only BFF forwarding contract
- `0b0742b` Stage 6.5 §6.5.1 CLOSED: ADR-027 Proposed

## Exact next action

1. Commit + push (this session, right after this SESSION_HANDOFF write).
2. On next session start: run the Colossus verify block above.
3. If green: append final `Stage 6.5.3 CLOSED · Colossus verified` BUILD_LOG entry with the timestamp, overwrite SESSION_HANDOFF for §6.5.4.
