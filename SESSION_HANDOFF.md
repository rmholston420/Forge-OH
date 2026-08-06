# Forge-OH — SESSION_HANDOFF

**Overwrite each session end.** Reflects CURRENT state only. Not append-only.

Last updated: **2026-08-06 09:29 EDT**

---

## Current stage/plugin/port

- **Stage 6.4c** · P1 Restart-from-here · **ADR-026 Ratified** (single-slice lock-in complete).
- Reconciliation-plan §6.4 fully closed at design + backend + frontend + e2e layers.

## What was completed this session

1. Backend closure (already committed at `7fc5fb1`): step 1e — service+router+verify all green. 45/45 pytest. `stage-6.4c-verify.sh` PASSED live on Colossus 2026-08-06 09:13 EDT.
2. Frontend closure (uncommitted, awaiting Colossus verify + push):
   - `RestartFromHereButton.tsx` — rules-of-hooks fix, sha-presence gate, ADR-026 §Frontend contract normative copy verbatim.
   - `page.tsx` — wired `commitShaAtTimeOfEvent` prop from `displayEv.commit_sha_at_time_of_event` (snake_case).
   - Unit vitest — DEFAULT_SHA helper, sha-gate tests (2 new), copy-guard rewritten for 3 ADR-026 outcomes.
3. BFF `debug.py` — E2E affordance: `extra.commit_sha_at_time_of_event` builds stub `sha_lookup` so synthesized events can be sha-eligible without touching the ledger. 3 new tests added.
4. New Playwright e2e `src/tests/e2e/run-restart-from-here.spec.ts` — positive + 2 negative cases + wire-body assertion + navigation assertion + dialog-copy screenshot.
5. `docs/adr/026-restart-from-here.md` — status flipped `Proposed` → `Ratified` with amendment block.

## What remains before DoD is met

**Colossus verify amend result** — the closure slice (`9eb10ce`) was amended by `HEAD` after a `toDisplayEvent` projection bug hid the button on Playwright.  Re-run only the Playwright leg + the `stage-6.4c-verify.sh` regression:

```bash
cd ~/dev/forge-oh && git pull --ff-only origin main
# no BFF/frontend rebuild needed if next-server is still running fresh; rebuild if in doubt.
cd ~/dev/forge-oh/src
PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
  npx playwright test tests/e2e/run-restart-from-here.spec.ts --reporter=list
bash ~/dev/forge-oh/scripts/stage-6.4c-verify.sh
```

### Historical (already green in prior verify run)


- pytest 56/56 (`test_debug_inject_endpoint.py` including 3 new synthetic-sha tests + `test_runs_restart.py` + `test_runs_sha_capture.py`).
- vitest 14/14 (`domain-RestartFromHereButton.test.tsx`).
- `stage-6.4c-verify.sh` PASSED live (happy + neg A + neg C).

### Only remaining

Playwright leg on the amended `toDisplayEvent`.  If green → Stage 6.4c DoD **CLOSED**.  If red → amend again (single-slice rule).

## Open questions / ambiguity

**None.** User answered all clarifications this session:
- Verify + ratify + add Playwright e2e.
- ADR-026 copy is normative.
- Sha gating: fix now.
- Hooks bug: fix now.

## Next exact action

**Re-run Playwright + regression on the amended HEAD.  On green, no further action.**

## Follow-up (out of scope for this slice)

- `ForkFromHereButton.tsx` shares the same rules-of-hooks bug pattern (`useCallback` after early return). Fix in a separate slice.
- Track under a new BUILD_LOG entry — not this one.
