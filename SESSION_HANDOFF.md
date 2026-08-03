# SESSION_HANDOFF.md

## Current stage
**Slice F complete.** Tagged `v1.0-alpha3`. Rec #3 Trajectory Memory
end-to-end: schema → store → embedder → retriever → writer + indexer →
BFF endpoints → STOP hook → Overview widget → ADR + E2E.

## Completed this session
- **F.1** schema — `556917f`
- **F.2** SQLite store — `bdbca9d`
- **F.3** bge-code-v1 embedder — `66d5dcd`
- **F.4** retriever (0.7 semantic + 0.3 symbol) — `c5aff52`
- **F.5** writer + indexer — `535f03f`
- **F.6** BFF endpoints — `3b4d39c`
- **F.5b** run-completion hook — `e507c87`
- **F.7** Overview widget — `4968d17`
- **F.8** ADR-008 + Playwright E2E + tag `v1.0-alpha3` — this commit

**Test totals:**
- Backend: 260 passed
- Frontend unit: 838 passed (1 pre-existing jsdom flake unrelated)
- E2E: 2 new specs (skip-guarded, run when Colossus has scratch DB env)

## Big picture
Recommendations 1, 2, and 3 all shipped and tagged:
- **Rec #1** — RepoGraph (Slice D) — `v1.0-alpha1`
- **Rec #2** — VerifyLoop (Slice E) — `v1.0-alpha2`
- **Rec #3** — Trajectory Memory (Slice F) — `v1.0-alpha3`

## How to exercise Slice F end-to-end on Colossus
```
# Backend
FORGE_OH_TRAJECTORY_DB=~/.forge-oh/trajectories.db \
  .oh-venv/bin/uvicorn bff.main:app --port 8081

# Frontend
echo 'NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY=true' >> .env.local
npm run dev

# E2E (scratch DB — never touches real memory)
FORGE_OH_TRAJECTORY_DB=/tmp/forge-oh-e2e-traj.db \
NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY=true \
  npx playwright test src/tests/e2e/trajectory-memory-panel.spec.ts
```

## Runtime wiring reminder
The trajectory STOP hook is a **separate subprocess** from the verify
STOP hook. Register both — they must both run on `HookEventType.STOP`,
verify first (writes verify-state.json), trajectory second (reads it
plus the sidecar).

Optional: `FORGE_OH_TRAJECTORY_INDEX_INLINE=1` to have the hook
immediately populate embeddings. Otherwise `TrajectoryIndexer.index_pending()`
should be called on a schedule (script pending — not in scope for
this slice).

## Open questions
None for Slice F. Deferred to future ADRs:
- Retention policy for `trajectories.db` (currently unbounded).
- Cross-machine sync (currently out of scope — local-first).
- Background drain schedule for the indexer.

## Next action
Choose the next slice. Candidates from the action plan not yet built:
- Any post-F recommendations in `Forge-OH-Action-Plan-v4.md` beyond
  the three that are now shipped.
- Runtime wiring the two STOP hooks into the agent server config on
  Colossus (not a slice — a config change).
- The indexer drain schedule.
