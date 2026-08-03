# ADR 006: RepoGraph — Repository-Aware Structural Retrieval

**Date:** 2026-08-03
**Status:** Accepted
**Related:** Forge-OH-Improvements-Research.md § Recommendation #1;
Forge-OH-Action-Plan-v4.md § Step 8

## Context

Semantic embeddings alone miss structural relationships between code
symbols. Callers/callees, file co-change frequency, and PageRank over the
call graph are known to substantially improve code-retrieval precision
for autonomous coding agents ([RepoGraph, arXiv:2410.14684]; Sourcegraph
Cody, GitHub Copilot Workspace).

For Forge-OH's local-first single-user architecture on Colossus (RTX
5090, 128GB RAM), we want:

1. A structural graph over the workspace with symbols, files, and calls.
2. PageRank-ranked context bundles the LLM can consume.
3. Callers/callees + git-history co-change signals for the UI.
4. No cloud graph databases, no CI dependency, no multi-user assumptions.

## Options Considered

- **A. Structural port of RepoGraph.**
  Re-implement the algorithm in clean Python + BFF endpoints; use
  tree-sitter for parsing; store in a local graph DB. Full control, no
  upstream RCE risks, clean license story.
- **B. Vendor RepoGraph upstream verbatim.**
  Fastest, but the upstream (`ozyyshr/RepoGraph`) has `exec()` and
  `eval()` calls in its graph-search paths, is Python-only, and hasn't
  seen a commit in 12 months. Unacceptable for a security-conscious
  local agent.
- **C. Use a hosted service (Sourcegraph, Cody).**
  Violates the local-first / single-user / no-cloud-control-plane rule.

## Decision

**Chose A — structural port.** No upstream code was copied; RepoGraph
upstream (`6c3977d8`, MIT) was read for reference only. See
[PORTING_LEDGER.md](../../PORTING_LEDGER.md) for the exact provenance
notes.

### Component layout

- `openhands_tools_ext/repograph/parser.py` — tree-sitter tag extractor
  (Python, TS, TSX, JS). Public API: `extract_tags(fname, rel_fname=None,
  *, source=None) -> list[Tag]`.
- `openhands_tools_ext/repograph/index.py` — file walker + graph builder
  + pure-Python PageRank (dropped `networkx` dep in favour of a 40-line
  power iteration).
- `openhands_tools_ext/repograph/store.py` — Neo4j reader/writer.
  `Neo4jStore.replace_repo(idx)` is idempotent (DETACH DELETE + MERGE in
  one tx).
- `bff/routers/repograph.py` — six endpoints under `/api/repograph`:
  `health`, `index`, `search`, `callers`, `callees`, `co_changed`,
  `context_bundle`.
- `bff/services/repograph_registry.py` — thread-safe in-memory
  `repo_key -> workspace_path` map for the `co_changed` git shell-out.
- `src/features/repograph/` + `src/components/domain/RepoGraphPanel.tsx`
  — frontend Trace-tab panel with typed hooks over the six endpoints.

### Storage: DozerDB (Neo4j-compatible)

Chose **DozerDB 5.26.27** running locally in `kosmos-dozerdb` container
over the raw Neo4j Community edition. Reasons:

- Bolt/Cypher wire-compatible with the standard `neo4j` Python driver.
- Extra APOC procedures pre-installed (useful for future graph
  algorithms).
- Same license (GPLv3 for community, but the driver we use is Apache
  2.0 — we do not distribute the DB).

The BFF talks to it via `bolt://localhost:7687` with credentials read
from `.env.neo4j` (chmod 600, gitignored). A dedicated database named
`forgeoh` isolates the graph from the surrounding Kosmos data.

Note: DozerDB reports `edition=enterprise` at the Cypher level even
though its container packaging says community. Logged in DEBUG_LOG.md.

### Feature flags

Gated at two layers:

- Backend: `REPOGRAPH_ENABLED=true` in `.env` on Colossus. When off,
  every `/api/repograph/*` endpoint returns 503.
- Frontend: `NEXT_PUBLIC_FEATURE_REPOGRAPH=true`. When off, the panel
  renders a stub explaining how to enable.

Either flag being off cleanly disables the feature.

### PageRank

Pure-Python power iteration in
`openhands_tools_ext/repograph/index.py::_power_iteration_pagerank`.
Damping = 0.85, tolerance = 1e-6, max 100 iterations. On the Forge-OH
repo itself (420 files, ~1000 symbols, ~2500 resolved calls) this runs
in well under a second.

### Search

`search_by_name` matches both `Symbol.name` AND `Symbol.rel_path` (OR).
Users naturally search by filename and symbol interchangeably; matching
only names created a UX gap when the query was a file segment (e.g.
`run_metadata`). See DEBUG_LOG.md 2026-08-03 07:39 EDT.

## Consequences

**Positive**
- No cloud dependency, no external code copied, clean MIT-referenced
  provenance.
- Six typed BFF endpoints give the UI + OpenHands tool a stable
  contract.
- 77 tests (26 router + 51 tool_ext) plus 14 frontend tests exercise
  the full stack from Cypher through to React.
- Real-repo smoke on Forge-OH itself worked first try: 420 files, 997
  symbols indexed in ~0.6s; top-hub `run_metadata_store.get` correctly
  ranked at PageRank 0.135.

**Negative / trade-offs**
- Neo4j is another moving part (a container) that must be running for
  RepoGraph to work. Mitigated: feature-flag gate + health endpoint that
  tells the UI exactly why it's unavailable.
- The workspace registry is in-memory — a BFF restart requires the user
  to re-index. Acceptable for single-user local; if the pain grows,
  persist to `.forge/repograph_registry.sqlite`.
- Only Python, TS, TSX, JS are indexed by the tag extractor. Adding
  languages (Go, Rust) requires new tree-sitter grammars + query files.

**Follow-ups**
- Autoindex-on-run: when a run starts against a workspace, call
  `/api/repograph/index` in the background so the panel is ready by the
  time the Trace tab loads.
- OpenHands tool wrapper: expose `context_bundle` as an OH tool so the
  agent can query the graph mid-run.

## References

- Forge-OH-Improvements-Research.md § Recommendation #1 (Perplexity
  Deep Research, 2026-08-02).
- RepoGraph upstream: https://github.com/ozyyshr/RepoGraph (commit
  `6c3977d8`, MIT). Read for reference only.
- PORTING_LEDGER.md entry #1.
- BUILD_LOG.md entries 2026-08-02 through 2026-08-03 for the D.1-D.5
  slice sequence.
