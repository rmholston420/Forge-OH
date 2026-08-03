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


---

## 2. LDB (`FloridSleeves/LLMDebugger`)

- **Slice:** E.3 (Recommendation #2, Execution-Verified Self-Debugging Loop)
- **Upstream:** [FloridSleeves/LLMDebugger](https://github.com/FloridSleeves/LLMDebugger)
- **Commit hash at time of reference:** `49ac191f181d47911cf38e5b9944fbbe6d4a6e60`
- **SPDX license:** `Apache-2.0`
- **Paper:** Zhong, Wang, Shang, *Debug like a Human: A Large Language Model Debugger via Verifying Runtime Execution Step-by-step*, ACL 2024, [arXiv:2402.16906](https://arxiv.org/pdf/2402.16906.pdf).
- **Port type:** **reference-only** — no upstream code was copied. Our `openhands_tools_ext/verify/breakpoint/inspector.py` is a fresh implementation of the same idea.
- **What we adapted (design points, not code):**
  1. The core LDB insight: an LLM debugging by inspecting **runtime state per block** beats reasoning over static code alone (paper §3, §5). Our inspector records `frame.f_locals` at each hit so the agent gets that runtime state.
  2. The "one block per hit with an inline `k=v; k=v; …` local-variable line" transcript shape (`programming/tracing/tracer.py::get_trace_line` + prompt templates in `programming/generators/prompt.py`). Our `summarize_for_llm` mirrors that.
  3. Bounded output size to keep the transcript LLM-context-safe (LDB does this inside their prompt template; we make it an explicit `MAX_HITS`/`MAX_REPR_LEN` constant).
- **Why we did not vendor upstream code:**
  1. **Interactive-loop shape.** LDB is built as a CLI/benchmark harness that runs one program per invocation via a hard-coded `.tmp.py` path in `programming/tracing/tracer.py::run_gt_traced` and `programming/ldb.py`. Not usable inside the OpenHands sandbox, which needs to inspect arbitrary user scripts.
  2. **Heavy dependencies.** Upstream requires `astroid` (Python static-analysis lib, ~3 MB) and vendors `staticfg` (a 700-LOC control-flow-graph builder) purely to auto-select breakpoints at basic-block boundaries. For our use case the *agent* decides which lines to inspect (informed by a failing traceback), so we do not need automatic CFG-block segmentation.
  3. **`pdb.Pdb` vs. `sys.settrace`.** LDB uses `pdb.Pdb`-derived subclasses via their `staticfg` helpers, which are interactive-loop shaped and block on stdin. `sys.settrace` gives us the same per-line callback with no interactive coupling and no dependency footprint.
  4. **Benchmark-specific code.** Roughly half of the upstream Python tree (`programming/generators/`, `programming/executors/`, `programming/main.py`, `programming/simple.py`, `programming/repeat_simple.py`) is dedicated to running HumanEval / MBPP / TransCoder benchmarks and is completely irrelevant to Forge-OH's live-run use.
  5. **Apache-2.0 attribution obligation without upside.** Because none of the upstream code fits our sandbox model, vendoring would add a compliance obligation (headers, NOTICE, LICENSE copy) with zero code reuse — pure overhead.
- **Files reviewed (reference-only) locally at `/home/user/workspace/ldb-upstream/`:**
  - `programming/tracing/tracer.py` (447 LOC — trace format inspiration).
  - `programming/tracing/staticfg/{builder,model}.py` (~700 LOC — not needed).
  - `programming/generators/prompt.py` (transcript template shape).
- **Our implementation:** [`openhands_tools_ext/verify/breakpoint/inspector.py`](openhands_tools_ext/verify/breakpoint/inspector.py) + 11 tests in [`openhands_tools_ext/tests/verify/breakpoint/test_inspector.py`](openhands_tools_ext/tests/verify/breakpoint/test_inspector.py).
- **Related ADR:** planned in E.5 (`docs/adr/007-verify-loop.md`).
