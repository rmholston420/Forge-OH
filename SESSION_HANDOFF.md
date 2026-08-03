# SESSION_HANDOFF.md

## Current stage
**Step 8, Slice F** — Rec #3 Trajectory Memory & Case-Retrieval.
Backend is complete. Next up: **F.7 (Overview widget)** then F.8 (ADR-008 + Playwright E2E + tag `v1.0-alpha3`).

## Completed this session
- **F.1** schema — commit `556917f`
- **F.2** SQLite store — commit `bdbca9d`
- **F.3** bge-code-v1 embedder — commit `66d5dcd`
- **F.4** retriever (0.7 semantic + 0.3 symbol) — commit `c5aff52`
- **F.5** writer + indexer — commit `535f03f`
- **F.6** BFF endpoints — commit `3b4d39c`
- **F.5b** run-completion hook — commit `e507c87`

**Test totals:** 260 passed (backend + trajectory router). 7 pre-existing `bff/tests/test_plugins_router.py` failures (upstream OH server dependency) unrelated to this slice.

## Slice F architecture summary
```
STOP event
  → verify/hook.py writes verify-state.json
  → trajectory/hook.py reads verify-state + trajectory-sidecar.json
     → TrajectoryWriter.write_from_run(RunSummary)
     → (optional) TrajectoryIndexer.index_pending()

Overview tab (upcoming F.7)
  → POST /api/trajectories/search  {task, symptom, k, current_symbols, ...}
  → TrajectoryRetriever  =  0.7 * cosine(bge-code-v1) + 0.3 * jaccard(symbols)
```

## Storage
- Store: `~/.forge-oh/trajectories.db` (env override `FORGE_OH_TRAJECTORY_DB`)
- WAL journal, 5s busy timeout, float32-packed embedding blob (1536-dim = 6144B)
- Sidecar contract: `.forge-oh/trajectory-sidecar.json` keyed by session_id

## Slice F decisions (locked)
1. Embedder: BAAI/bge-code-v1 (1536-dim), fallback nomic-embed-text via Ollama only if `torch.cuda.is_available()` False.
2. Storage: separate `~/.forge-oh/trajectories.db`, NOT BFF's DB.
3. Retrieval weights: 0.7 semantic + 0.3 symbol overlap (convex).
4. Writer trigger: distinct run-completion hook (`openhands_tools_ext.trajectory.hook`), not the verify STOP hook.
5. Widget placement: Overview tab, top, proactive display before agent context.

## Next action
**F.7 — Overview widget.** Location: `src/features/run-detail/` new subdirectory `trajectory-memory/` with:
- `TrajectoryMemoryPanel.tsx` — top-of-Overview card, shows top-k hits when `run.task` is available
- `useTrajectorySearch.ts` — React Query hook wrapping `POST /api/trajectories/search`
- `trajectory-api.ts` — thin fetch wrapper using `zod.parse(TrajectoryRecordSchema)` from `src/lib/schemas/trajectory.ts`
- Playwright test at F.8.

Entrypoint in `src/app/(dashboard)/runs/[runId]/page.tsx` — mount inside `selectedTab === 'overview'` block **above** the timeline layout.

## Open questions
None. All Slice F decisions locked in earlier this session; F.5b implemented as separately-registered hook per decision #4.
