# PORTING_LEDGER

Log of every OSS component vendored, structurally ported, or referenced
by Forge-OH. Append-only. One entry per source.

Format per entry:

```
## <YYYY-MM-DD> — <component name>
- **Source URL:** <upstream URL>
- **Commit:** <sha>
- **License:** <SPDX>
- **Kind:** verbatim-vendor | structural-port | reference-only
- **Location(s):** <paths in this repo>
- **Modifications:** <what changed vs upstream, and why>
- **Related ADR:** <docs/adr/NNN-*.md>
```

---

## 2026-08-03 — RepoGraph

- **Source URL:** https://github.com/ozyyshr/RepoGraph
- **Commit:** `6c3977d8` (pinned at project start of Slice D)
- **License:** MIT (SPDX: `MIT`)
- **Kind:** reference-only (no upstream code copied)
- **Location(s):**
  - `openhands_tools_ext/repograph/parser.py` (Slice D.2)
  - `openhands_tools_ext/repograph/index.py` (Slice D.3)
  - `openhands_tools_ext/repograph/store.py`  (Slice D.3)
  - `bff/routers/repograph.py`                 (Slices D.1 + D.4)
  - `bff/services/repograph_registry.py`       (Slice D.4)
  - `src/features/repograph/`                  (Slice D.5)
  - `src/components/domain/RepoGraphPanel.tsx` (Slice D.5)

- **Modifications vs upstream:**
  Upstream (`construct_graph.py`, `graph_searcher.py`, `utils.py`) was
  read for reference only — **no code was copied**. Reasons for the
  structural port instead of a verbatim vendor:

  1. Upstream `graph_searcher.py` contains `exec()` and `eval()` calls
     on user-influenceable strings (remote-code-execution risk in a
     local agent).
  2. Upstream is Python-only via `tree_sitter_languages`, which is
     unmaintained and stuck on old grammars. We use `tree_sitter` +
     `tree_sitter_languages` at pinned versions and added TS/TSX/JS
     tag queries alongside Python.
  3. Upstream stores the graph as an in-memory `networkx.MultiDiGraph`.
     We store in Neo4j (DozerDB) so the UI and OpenHands tool can query
     it via Cypher across restarts.
  4. Upstream computes PageRank via `networkx.pagerank`. We dropped the
     `networkx` dep entirely and implemented a 40-line pure-Python power
     iteration (`_power_iteration_pagerank` in
     `openhands_tools_ext/repograph/index.py`).
  5. Upstream has no BFF, no feature flags, no HTTP contract. Our six
     endpoints in `bff/routers/repograph.py` are original design work.

  The only conceptual borrowings are:
  - Tag-based symbol extraction from tree-sitter S-expression queries
    (a widely-used pattern, also used by aider, Sourcegraph, and many
    others).
  - PageRank over the call graph as the ranking signal (published in
    the RepoGraph paper, arXiv:2410.14684, and generally-known).
  - The idea of a `context_bundle` seeded from a set of files and
    expanded via graph neighborhood (structurally similar to
    RepoGraph's paper description, but our implementation is a fresh
    Cypher query).

- **Related ADR:** [docs/adr/006-repograph.md](docs/adr/006-repograph.md)
