# ADR-008: Trajectory Memory & Case-Retrieval

- **Status:** Accepted
- **Date:** 2026-08-03
- **Slice:** F (Recommendation #3, Forge-OH-Action-Plan-v4)
- **Related:** ADR-006 (RepoGraph, Rec #1); ADR-007 (VerifyLoop, Rec #2);
  [PORTING_LEDGER.md](../../PORTING_LEDGER.md) entry #3 (bge-code-v1).

## Context

Before Slice F, every Forge-OH run started from a blank slate. Even
when the agent had already solved the same task, the same flake, or
the same class of error on this workstation an hour earlier, the next
run had no way to see it. The agent's only "memory" was whatever
happened to be in its rolling context window at the moment.

Rec #3 in the plan asks for a **case-retrieval memory**: on every
completed run, persist a structured record — task, plan, diffs,
verify iterations, symbols touched, final status, symptom — into a
local store, then proactively surface the top-*k* nearest prior cases
at the start of the next run.

The retrieval budget is small on purpose. This is a hint layer, not a
long-term-memory replacement.

## Decision

### 1. Local-first storage, separate SQLite DB

`~/.forge-oh/trajectories.db` (env override
`FORGE_OH_TRAJECTORY_DB`, then `OPENHANDS_PROJECT_DIR/.forge-oh/`,
then `~/.forge-oh/`), SQLite with WAL and a 5s busy timeout. Embedding
column is a float32 packed BLOB, 1536 dimensions.

Explicitly **not** the BFF database. The BFF DB is for run state and
short-lived UI queries; trajectories are a long-lived, single-user,
append-mostly memory store that we want to survive BFF resets,
schema wipes, and container recreations. Keeping it separate also
means the frontend never accidentally joins across it.

### 2. Embedding model: `BAAI/bge-code-v1`

1536-dim, code-aware, permissive license (Apache-2.0). Runs locally
on Colossus via `sentence-transformers` on top of the same PyTorch /
CUDA 13 stack already installed for other tooling. See
`PORTING_LEDGER.md` entry #3 for source, commit, and license.

Fallback: `nomic-embed-text` via Ollama when `torch.cuda.is_available()`
is false. Not wired in F.3 by default because Colossus has the GPU;
the code path exists so a CPU-only clone still runs.

Chosen over OpenAI `text-embedding-3-*` because Forge-OH is
local-first and never talks to a cloud control plane for a core
workflow. Chosen over generic English embeddings (e5, gte, jina)
because the task descriptions are heavily code-flavored and the
symbol overlap term (below) already covers structure — the semantic
term has to earn its weight on prose-in-a-code-context, which is
exactly what bge-code-v1 was trained for.

### 3. Retrieval: co-ranked semantic + symbol overlap

Score of a candidate record against a query:

```
score = 0.7 * cosine(embed(query.task), record.embedding)
      + 0.3 * jaccard(query.current_symbols, record.repograph_symbols)
```

Weights are `schema.SEMANTIC_WEIGHT` and `schema.SYMBOL_WEIGHT`,
constant module-level exports so both the retriever and any future
re-ranker read them from one place.

**Why co-ranking, not cascading:** pure semantic retrieval is fooled
by tasks that read alike but touch a totally different area of the
codebase (e.g. two different "fix flaky auth" runs against different
plugins). Pure symbol overlap is fooled by tasks that touch the same
files for completely different reasons (config change vs. bugfix).
The convex combination lets each catch the other's failure mode
without either being able to dominate.

**Verified-only by default:** the search endpoint defaults
`verified_only=true`, so a failed run whose failure was itself
unverified (e.g. verify loop hit `no-step`) never suggests itself as
a prior case. A `verified_failure` — the verify loop ran and the
tests still failed — *does* surface, because "we tried this and it
didn't work" is a useful hint too.

### 4. Writer trigger: distinct run-completion STOP hook

Trajectory writing runs as a **separate STOP subprocess** alongside
the verify hook, not inside it:

```
openhands_tools_ext.verify.hook       # writes verify-state.json
openhands_tools_ext.trajectory.hook   # reads verify-state + sidecar,
                                      # writes trajectory record
```

Both are registered as `HookType.COMMAND` on STOP. The trajectory
hook runs after the verify hook because it reads the verdict the
verify hook just wrote.

**Sidecar contract:** `$OPENHANDS_PROJECT_DIR/.forge-oh/trajectory-sidecar.json`,
top-level dict keyed by session_id (same layout as verify-state.json).
The agent server (or an earlier hook) populates it with
`task_description`, `plan`, `symptom`, `repograph_repo_key`,
`repograph_symbols`, `diffs`, `verify_iterations`. Absent = hook
still runs, with best-effort empty fields (falls back to
`OPENHANDS_TASK` env).

**Never blocks the agent.** Exit 0 on success, 1 on hard input
failure only. Malformed JSON, missing session id, non-STOP events
are all treated as no-ops. Trajectory data is nice-to-have; a broken
hook can't take a run down.

**Idempotent.** `traj_{run_id}` is the primary key; a second STOP for
the same run replaces the record.

**Optional inline indexing:** `FORGE_OH_TRAJECTORY_INDEX_INLINE=1`
runs `TrajectoryIndexer.index_pending()` inside the hook so the
record is searchable immediately. Off by default — the indexer is
cheap but not zero, and the widget only reads records with embeddings
so a background drain is fine.

### 5. Widget placement: Overview tab, top, proactive

The case-retrieval widget renders **above** the event timeline on the
run detail Overview tab, before the agent has produced any events.
It queries `POST /api/trajectories/search` with the current run's
`title` as the task description and excludes the current run id from
results.

Placement was the last decision to lock. Considered:

- **Trace tab, alongside RepoGraph.** Rejected — the Trace tab is
  post-hoc explain, not up-front hint. Prior cases are most valuable
  before the agent starts, not after.
- **A modal on run creation.** Rejected — modals interrupt; a passive
  panel at the top of the run page is glanceable and dismissable by
  scrolling.
- **A separate "Memory" tab.** Rejected — anything behind a tab is
  effectively off. Proactive means the user sees it without asking.

The widget is feature-flag-gated on `FEATURE_TRAJECTORY_MEMORY`
(`NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY=true`), so the whole panel
can be turned off from the frontend without touching the writer or
the endpoints.

### 6. BFF surface: three plain endpoints, no envelope

Same pattern as RepoGraph (ADR-006):

- `GET  /api/trajectories?limit&status&repo_key` → `{total, records}`
- `GET  /api/trajectories/{trajectory_id}` → one record, or 404
- `POST /api/trajectories/search` — body is the query spec, response
  is `{query, k, hits}` with per-hit `{record, score, semantic_score,
  symbol_overlap}`

Plain Pydantic response models — no `{data: ...}` envelope. Bounds
enforced at the schema layer (`k` in 1..25, `limit` in 1..500) so
422 comes back before any DB hit.

Store lifecycle is a module-level singleton in
`bff/deps/trajectory_store.py`, following the same pattern as the
Neo4j driver dep. Tests override it via
`app.dependency_overrides[get_trajectory_store]`.

### 7. Zod parity

Every response type is mirrored in `src/lib/schemas/trajectory.ts`
and Zod-parsed after `unwrap()` in the feature client. Backend
schema is the source of truth; drift is guarded by
`openhands_tools_ext/tests/trajectory/test_schema.py::TestFrontendParity`.

## Consequences

**Good**

- The agent gets a memory of what it has already tried on this
  workstation, without any cloud dependency and without a
  vector-DB service to run.
- The write path is decoupled from the agent's control loop — a
  broken hook, a missing sidecar field, or a corrupted verify-state
  file can never wedge a run.
- The retrieval score is transparent: each hit shows the semantic
  and structural components alongside the composite, so a
  suspicious top hit is inspectable at a glance.
- Placement is proactive — the user doesn't need to know the feature
  exists to benefit from it.

**Neutral**

- One more SQLite file to back up if the user wants durable memory
  across machine reinstalls. `~/.forge-oh/trajectories.db` is small
  (KB-per-run) and trivial to `rsync`.
- One more STOP subprocess spawned per run completion. Cheap; runs
  in parallel with (i.e., after) verify.

**Bad**

- The store grows without bound. F.8 does not implement retention.
  A future ADR will decide when (and whether) to prune, most likely
  by a `retention_days` env var or a max-count LRU. Present-day
  volume on Colossus is a few hundred records per week — nothing to
  worry about until it's ~1e5 records.
- No cross-machine sync. If the user runs Forge-OH on two workstations
  they get two separate memories. Deliberate — the sync problem is
  strictly out of scope for local-first.
- The embedder is heavy on first load (~500MB weights). Amortized
  via the lazy module-level singleton; subsequent calls in the same
  Python process are free.

## Alternatives considered

**Store trajectories inside the RepoGraph Neo4j.** Rejected —
RepoGraph is a repo-shaped structural index; trajectories are a
time-shaped memory. Different keys, different query patterns,
different lifetimes.

**Use the OpenHands SDK's built-in memory abstraction.** Inspected;
too coupled to the SDK's own conversation-summary format, and would
have made the writer sensitive to SDK internal churn. A local
SQLite + a hook is a smaller surface.

**Skip the symbol overlap term, use pure semantic.** Rejected — see
§3. Too easy for the semantic model to be fooled by prose
similarity across unrelated code paths.

**Blocking STOP hook that fails the run on write error.** Rejected —
the agent must not become dependent on the memory writer being
healthy. See §4.

## Ports & external code

None. Everything in Slice F is written directly:

- `openhands_tools_ext/trajectory/schema.py` — Pydantic models,
  parity-tested against `src/lib/schemas/trajectory.ts`.
- `openhands_tools_ext/trajectory/store.py` — SQLite writer,
  WAL journaling.
- `openhands_tools_ext/trajectory/embedder.py` — bge-code-v1 loader
  (lazy singleton) + fake encoder for unit tests.
- `openhands_tools_ext/trajectory/retriever.py` — co-ranked search.
- `openhands_tools_ext/trajectory/writer.py` — RunSummary → record
  ingestion + `TrajectoryIndexer` for embedding pending records.
- `openhands_tools_ext/trajectory/hook.py` — STOP CLI.
- `bff/routers/trajectories.py` — three endpoints.
- `bff/deps/trajectory_store.py` — store singleton.
- `src/features/trajectory-memory/{api,hooks}.ts` — frontend client.
- `src/components/domain/TrajectoryMemoryPanel.tsx` — widget.

Only external dependency added to `.oh-venv` is `sentence-transformers`
3.4.1 + its transitive `transformers` 4.57.6 pin — see
PORTING_LEDGER.md #3.
