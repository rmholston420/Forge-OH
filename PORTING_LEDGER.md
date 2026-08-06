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


---

## 3. Qwen3.6-27B INT4 AutoRound (Lorbus)

- **Slice:** F.1b (Path F instrumented rebench) + ADR-013 amendment #1 (coder ratification)
- **Upstream:** [Lorbus/Qwen3.6-27B-int4-AutoRound](https://huggingface.co/Lorbus/Qwen3.6-27B-int4-AutoRound)
- **Base model:** [Qwen/Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) (`Qwen3.5MoeForCausalLM` architecture; 27B dense variant)
- **Quantization method:** [AutoRound](https://github.com/intel/auto-round) INT4 (Intel Neural Compressor). Weights packed as compressed-tensors int4; vLLM auto-detects from `config.json` — do NOT pass `--quantization` at launch.
- **SPDX license:** `Apache-2.0` (inherited from Qwen3 base model)
- **Port type:** **weights-only** — no upstream code was copied. Weights pulled to `$HOME/models/qwen3.6-27b-int4-autoround/` on Colossus via `bench/pathE_qwen36_27b/pull_models.sh` (2026-08-05, in prior session).
- **Runtime:** vLLM 0.10.2+ Docker (`vllm/vllm-openai:latest`). Launch flags in `ops/vllm_launch_coder.sh`:
  - `--tool-call-parser qwen3_coder` (Qwen3-Coder family tool-call schema)
  - `--enable-auto-tool-choice`
  - `--trust-remote-code` (Qwen3.5MoE custom modeling code)
  - `--enable-prefix-caching`
  - `--max-model-len 32768 --max-num-seqs 128 --gpu-memory-utilization 0.90`
- **VRAM envelope (F.1b, RTX 5090 32 GB, warm state):**
  - Peak VRAM: 29,701 MiB / 32,768 MiB (91% utilization)
  - Peak temperature: 71°C (RED cutoff 88°C, headroom 17°C)
  - Sustained power: 435-438 W (of 450 W TDP, 97% draw)
  - GPU util: 100% pinned during generation
- **Bench evidence:**
  - F.1b combined avg: 112.7/200 (rank #1 unanimous across Claude Fable 5, GPT 5.6 Sol, Gemini 3.1 Pro)
  - F.1b debug avg: 86.7/100 (only cell that correctly removed both dead import and `Depends(...)` usage lines)
  - F.1b arch avg: 26.0/100 (all 3 candidates failed the arch trap identically; 39.7-point margin over 3rd place preserved regardless)
- **Related ADRs:**
  - [docs/adr/013-qwen36-27b-canonical-coder-planner.md](docs/adr/013-qwen36-27b-canonical-coder-planner.md) — coder ratification (amendment #1)
  - [docs/adr/009-local-llm-selection.md](docs/adr/009-local-llm-selection.md) — superseded by ADR-013 for coder-selection layer
- **Rollback:** set `LLM_CODER_MODEL=qwen3.6-35b-nvfp4` and pass `--quantization modelopt_fp4` to `vllm_launch_coder.sh` (ADR-009 baseline).

---

## 2026-08-06 00:24 EDT — `react-force-graph-2d` — Stage 4.2/4.3 RepoGraph visualization

- **Slice:** Stage 4.2 (backend `/api/repograph/graph`) + Stage 4.3 (frontend force-directed view).
- **Upstream:** [vasturiano/react-force-graph](https://github.com/vasturiano/react-force-graph) — package `react-force-graph-2d`.
- **Version pin:** `^1.29.1` (latest at 2026-08-06 from `https://registry.npmjs.org/react-force-graph-2d`).
- **SPDX license:** `MIT`.
- **Port type:** **dependency-only** — no upstream source was copied. The library is added as a `dependencies` entry in `package.json`; no vendored code in `src/`.
- **Modification notes:** none. Wrapped in `next/dynamic({ ssr: false })` at `src/features/repograph/RepoGraphGraphView.tsx` so the canvas / d3 chain never touches the SSR pass.
- **Related files:**
  - `openhands_tools_ext/repograph/store.py::Neo4jStore.full_graph()` — server-side aggregator
  - `bff/routers/repograph.py::repograph_graph` — `GET /api/repograph/graph`
  - `src/lib/schemas/repograph.ts::RepoGraphFullGraphSchema` — Zod runtime contract
  - `src/features/repograph/RepoGraphGraphView.tsx` — force-directed view
  - `src/app/(dashboard)/repograph/page.tsx` — standalone `/repograph` route
- **Rollback:** remove the `react-force-graph-2d` line in `package.json`, delete `RepoGraphGraphView.tsx` and `src/app/(dashboard)/repograph/`, revert the Graph toggle branch of `RepoGraphPanel.tsx`. `full_graph()` and `GET /api/repograph/graph` remain callable without the view.

---

## 2026-08-06 00:53 EDT — Serena (LSPClient port) — Stage 4.4

- **Slice:** Stage 4.4 (`LSPClient` port via MCP passthrough).
- **Upstream:** [oraios/serena](https://github.com/oraios/serena).
- **Version pin (commit SHA):** `c7af2c09ef45faa4367c0e2a9f770fb73a62a612` (upstream `main` HEAD as of 2026-08-06 00:48 EDT). Recorded in `bff.settings.Settings.serena_pin_sha`.
- **SPDX license:** `MIT` (per upstream `LICENSE` file, verified from GitHub 2026-08-06). If a diligence check surfaces a different license, bump this entry and open a follow-up ADR.
- **Port type:** **dependency-only** — no upstream source was copied. Serena is fetched at runtime by `uvx` from the pinned Git URL on first `POST /api/mcp/serena/ping`.
- **Launch verb (canonical):**
  ```
  uvx --from git+https://github.com/oraios/serena@c7af2c09ef45faa4367c0e2a9f770fb73a62a612 \
      serena start-mcp-server --context ide-assistant --project <SERENA_WORKSPACE_DEFAULT>
  ```
  Transport: `stdio`. Context flag `ide-assistant` chosen per upstream README recommendation for embedded MCP clients.
- **Modification notes:** none. Registered as an MCP server via `POST /api/mcp` at BFF startup when `SERENA_ENABLED=true` (see `bff/services/mcp_bootstrap.py`).
- **Related files:**
  - `bff/settings.py::Settings.serena_*` — feature flag, workspace default, pin SHA
  - `bff/services/mcp_bootstrap.py::register_serena_if_missing` — idempotent startup registration
  - `bff/main.py` — lifespan hook that calls the bootstrap
  - `bff/services/event_normalize.py::_serena_op_from_tool_name` — promotes ActionEvent `type` to `lsp_<op>`
  - `src/components/domain/EventCard.tsx` — LSP badge + LSP-family icons
  - `docs/adr/018-serena-lspclient-integration.md` — design decisions and spec-diff record
- **Rollback:** set `SERENA_ENABLED=false` in `.env` and restart BFF. Registration coroutine no-ops. No frontend rollback needed — the LSP icons and badge are dead code when no LSP-typed events arrive.

## Kosmos `ops/compose/memory.yml` (referenced 2026-08-06 · Stage 4.5 · ADR-019)

- **Type:** dependency reference (not vendored). Forge-OH does not copy Kosmos code; this ledger entry records the cross-repo dependency locked by ADR-019.
- **Source:** `github.com/rmholston420/kosmos` — path `ops/compose/memory.yml`.
- **Pinned commit:** `c455165bca0d645f0d43572d0c286dca7033d31d` (Kosmos HEAD as of ADR-019 acceptance).
- **SPDX license:** MIT (Kosmos `pyproject.toml` → `license = { text = "MIT" }`).
- **What Forge-OH depends on:**
  - Container name `kosmos-dozerdb` and image `graphstack/dozerdb:5.26.27`.
  - Bolt endpoint `bolt://127.0.0.1:7687` (host port 7687).
  - HTTP endpoint `http://127.0.0.1:7474` (host port 7474).
  - APOC plugin available (`NEO4J_PLUGINS: '["apoc"]'`).
- **What Forge-OH does NOT depend on:**
  - Kosmos's exact password (`kosmos-dev-password`) — Forge-OH holds its own in `.env.neo4j`.
  - Kosmos's heap sizing — informational only.
- **Rollback / drift detection:** if Kosmos changes any of the "depended-on" items above, Forge-OH's `GET /api/repograph/health` breaks. Re-verify against the Kosmos file at the pinned SHA and either re-pin (updating this entry) or file a new ADR if the change is incompatible.
- **Migration to Option B (if ever required):** see ADR-019 D4 — Kosmos brings up a second DozerDB with a new container name and different port bindings; Forge-OH keeps its existing binding unchanged.

## 2026-08-06 01:39 EDT — Kosmos ports: memory.py, vector.py, embeddings.py
- Source: rmholston420/kosmos, commit c455165bca0d645f0d43572d0c286dca7033d31d
- Source paths: ports/memory.py, ports/vector.py, ports/embeddings.py
- Destination: openhands_tools_ext/memory/ports/
- Fetch method: raw.githubusercontent.com at pinned SHA (no clone); SHA-256 equality to upstream verified per file
- License/ownership: same-owner internal port (rmholston420 → rmholston420), logged for traceability per project convention
- Modification notes: zero modifications — files copied verbatim, no import-path edits were required (upstream files import stdlib only)
- Included exports beyond Protocols: memory.py ships MEMORY_REQUIRED_FIELDS + validate_zero_trust_write() + MemoryEventId/MemoryHit/MemoryWriteBlocked; vector.py ships REQUIRED_PAYLOAD_KEYS + validate_zero_trust_payload() + VectorHit/SnapshotHandle; embeddings.py ships EmbeddingError/EmbeddingDimensionMismatch. Stage 5.4 will reuse these existing zero-trust helpers rather than introducing a parallel pydantic model.

## 2026-08-06 01:44 EDT — Kosmos adapters: Qdrant VectorPort + Ollama EmbeddingsPort
- Source: rmholston420/kosmos, commit c455165bca0d645f0d43572d0c286dca7033d31d
- Source paths:
  - adapters/vector/qdrant/{__init__.py, adapter.py, real_backend.py, test_contract.py}
  - adapters/embeddings/ollama/{__init__.py, adapter.py, test_contract.py}
- Destination:
  - openhands_tools_ext/memory/adapters/vector/qdrant/
  - openhands_tools_ext/memory/adapters/embeddings/ollama/
  - bff/tests/memory/  (contract tests relocated so CI runs them)
- License/ownership: same-owner internal port (rmholston420 → rmholston420)
- Modification notes:
  - Imports rewritten mechanically: `ports.*` → `openhands_tools_ext.memory.ports.*`;
    `adapters.vector.qdrant` → `openhands_tools_ext.memory.adapters.vector.qdrant`;
    `adapters.embeddings.ollama` → `openhands_tools_ext.memory.adapters.embeddings.ollama`.
  - Env vars: `KOSMOS_OLLAMA_BASE_URL` → `OLLAMA_URL` and `KOSMOS_OLLAMA_EMBED_MODEL` → `OLLAMA_EMBED_MODEL`. Plan §5.2 said reuse `OLLAMA_BASE_URL`; that is Forge-OH's OpenAI-compat `/v1` prefix and would break the native `/api/embed` calls the adapter makes. Correct env var is `OLLAMA_URL` (native root, port 11434 with no suffix). Documented in the adapter docstring and `.env.example` (plan §5.2 correction, not a spec deviation).
  - Test env-var: `KOSMOS_STAGE_16_LIVE` → `FORGE_MEMORY_LIVE` for the Colossus live-tier smoke test.
  - No behavior changes; SHA-256 of each file body diff-verifiable against upstream after the mechanical rewrites listed above.

## 2026-08-06 01:57 EDT — ADR-020 amendment to Stage 5.2 Ollama embeddings adapter
Amendment to the Stage 5.2 Kosmos port (2026-08-06 01:44 EDT entry above): Forge-OH default embedder changed from Kosmos upstream `nomic-embed-text` to `qwen3-embedding:0.6b` per ADR-020 (`docs/adr/020-qwen3-embedding-default.md`). `qwen3-embedding:4b` also registered in the adapter's dimension table for opt-in A/B via `OLLAMA_EMBED_MODEL`. Adapter code + `.env.example` + one contract test updated to match. Kosmos re-sync of `adapters/embeddings/ollama/adapter.py` at any future SHA must preserve: (a) the three `qwen3-embedding:*` entries in `_MODEL_DIMENSIONS`, (b) the default fallback `qwen3-embedding:0.6b` in `__init__`, (c) the docstring env-var block noting ADR-020.

## 2026-08-06 02:10 EDT — Kosmos adapter: DozerDB SemanticMemoryPath (Stage 5.3a)
- **Source repo:** rmholston420/kosmos @ `c455165bca0d645f0d43572d0c286dca7033d31d`
- **Source paths:**
  - `adapters/memory/dozerdb/semantic_memory_path.py` (257 lines)
  - `adapters/memory/dozerdb/test_semantic_memory_path.py` (268 lines)
  - ADR-074 §D3 (design authority)
- **Destination paths:**
  - `openhands_tools_ext/memory/adapters/dozerdb/semantic_memory_path.py`
  - `openhands_tools_ext/memory/adapters/dozerdb/__init__.py`
  - `openhands_tools_ext/memory/adapters/dozerdb/smoke.py` (new — thin live smoke helper, not a plugin surface)
  - `bff/tests/memory/test_semantic_memory_path_contract.py`
- **License / ownership:** same-owner internal port (both repos owned by rmholston420); no third-party license triggered — `SemanticMemoryPath` is pure composition of Stage 5.1 ports with zero external deps.
- **Modification notes:**
  1. Mechanical import rewrite only: `from ports.{embeddings,memory,vector}` → `from openhands_tools_ext.memory.ports.{embeddings,memory,vector}`. Contract test additionally rewrites `from adapters.vector.qdrant.adapter` → `from openhands_tools_ext.memory.adapters.vector.qdrant.adapter` and `from adapters.memory.dozerdb.semantic_memory_path` → `from openhands_tools_ext.memory.adapters.dozerdb.semantic_memory_path`.
  2. Class body, method signatures, docstrings, and behavior are byte-identical to source.
  3. `smoke.py` is a Forge-OH-side thin helper that composes Stage 5.2's `OllamaEmbeddingsAdapter` + `QdrantVectorAdapter`/`RealQdrantBackend` with the ported `SemanticMemoryPath` for §5.3.4's live-smoke command. It is NOT a plugin surface and will be removed / superseded by `DozerDbMemoryAdapter.search_semantic` in Stage 5.3b.
- **Stage 5.3a stop condition:** Reached — 11 new contract tests green under both default (`qwen3-embedding:0.6b`) and A/B override (`qwen3-embedding:4b`); full memory suite now 54 passed / 1 skipped in both configurations. Live-tier verification against real Ollama + Qdrant remains for Colossus.
- **Deferred to 5.3b:** `DozerDbMemoryAdapter` (552 lines), `dozerdb_graph_backend.py` (215 lines), `amg_policy.py` (218 lines), their contract tests, and dependency pulls for `neo4j` + `graphiti-core` + `agent_memory_guard`.

## 2026-08-06 02:32 EDT — Kosmos DozerDB MemoryPort adapter + graph backend + contract test (Stage 5.3b)
- **Source repo:** rmholston420/kosmos @ `c455165bca0d645f0d43572d0c286dca7033d31d`
- **Source paths (Kosmos):**
  - `adapters/memory/dozerdb/adapter.py` (552 lines)
  - `adapters/memory/dozerdb/dozerdb_graph_backend.py` (215 lines)
  - `adapters/memory/dozerdb/test_contract.py` (442 lines)
- **Destination paths (Forge-OH):**
  - `openhands_tools_ext/memory/adapters/dozerdb/adapter.py`
  - `openhands_tools_ext/memory/adapters/dozerdb/dozerdb_graph_backend.py`
  - `bff/tests/memory/test_dozerdb_memory_adapter_contract.py`
  - `openhands_tools_ext/memory/adapters/dozerdb/__init__.py` (extended to re-export new symbols)
- **NOT ported (deliberate):**
  - `adapters/memory/dozerdb/amg_policy.py` — holds `AmgGuardPolicy` + `AmgV02Policy`, both require the `agent-memory-guard` PyPI dep. Forge-OH ADR-021 D5 wires `NoOpAmgPolicy` (which lives in `adapter.py`), so the guard implementation stays out.
  - `adapters/memory/dozerdb/amg_v02_policy.py` — backward-compat shim for the above; unused in Forge-OH.
- **New Forge-OH-side code (not from Kosmos):**
  - `openhands_tools_ext/memory/adapters/dozerdb/dozerdb_temporal_index.py` (~245 lines) — plain-Cypher TemporalIndex per ADR-021 D2/D3. Replaces Kosmos's ADR-075-D1-deleted `GraphitiTemporalIndex`.
  - `openhands_tools_ext/memory/composition.py` (~130 lines) — Forge-OH composition root reading Forge-OH-side env vars (`NEO4J_BOLT_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `OLLAMA_URL`, `QDRANT_URL`, `FORGEOH_MEMORY_CORPUS`). Kosmos has no direct analog — Kosmos composes at kernel boot.
  - `openhands_tools_ext/memory/adapters/dozerdb/smoke.py` — extended with `roundtrip()` for Stage 5.3b DoD live smoke; `search_semantic()` retained for Stage 5.3a regression parity.
- **License / ownership:** same-owner internal port (rmholston420 → rmholston420). No third-party license triggered by the ports; the deliberate NOT-ported files would have been Apache-2.0 (`agent-memory-guard`), sidestepped here.
- **Modification notes (mechanical):**
  1. Import rewrites: `from ports.{embeddings,memory,vector}` → `from openhands_tools_ext.memory.ports.{embeddings,memory,vector}`; `from adapters.memory.dozerdb.*` → `from openhands_tools_ext.memory.adapters.dozerdb.*` (adapter.py, test_contract.py).
  2. Module-header docstring rewritten to name Forge-OH module path, cite ADR-021 (Stage 5.3b), and remove references to now-deleted Graphiti / not-ported AMG PyPI dep.
- **Modification notes (semantic — non-mechanical):**
  1. **Graph shape:** Kosmos's `write_event` (adapter.py lines 394–412) already implements the CIDOC-CRM reified-event star topology that ADR-021 D1 calls for (A2 + α). Concretely: `(:Entity {role:'subject'})` + `(:MemoryEvent)` + `(:Entity {role:'object'})` with `[:SUBJECT_OF]`/`[:OBJECT_OF]` edges. Zero shape-code changes — my initial ADR-021 draft was hand-designed and inferior; the draft was amended in-place on the same day to inherit Kosmos's shape. See ADR-021 status-amendment block at top of `docs/adr/021-memory-adapter-graph-shape.md`.
  2. **Temporal index:** Kosmos's `GraphitiTemporalIndex` was hard-deleted at pinned SHA (ADR-075 D1). Replaced with a new Forge-OH `DozerDbTemporalIndex` that (a) is a no-op on `record_event` since the graph write already emits searchable properties on the `:MemoryEvent` node, and (b) queries via Lucene fulltext over the co-located `:MemoryEvent` nodes with the ADR-021 D2 DDL: `memory_event_text` FULLTEXT INDEX + `memory_event_written_at` RANGE INDEX + `memory_event_id_unique` uniqueness constraint. Lucene queries pass through `_escape_lucene` so callers pass plain natural-language text.
  3. **AMG dep sidestep:** `NoOpAmgPolicy` from Kosmos's `adapter.py` is re-exported and wired at composition root. Guard-active policy layer is preserved architecturally; can be enabled later without a shape change.
- **Contract test compatibility:** Kosmos's 442-line contract suite runs Forge-OH-side unchanged (42 test IDs — Kosmos's exact test set). Suite uses `NoOpAmgPolicy` + `InMemoryGraphBackend` + `InMemoryTemporalIndex`, all of which live in `adapter.py` and port verbatim.
- **Verification:**
  - `bff/tests/memory/test_dozerdb_memory_adapter_contract.py`: **42 passed**
  - Full memory suite (`bff/tests/memory/`): **96 passed, 1 skipped** under both baseline embedder and `OLLAMA_EMBED_MODEL=qwen3-embedding:4b`
  - Colossus live-tier round-trip smoke: pending user pull + `pip install neo4j>=5.26` in `.oh-venv`
- **Deferred (not blocking 5.3b):**
  - qdrant-client 1.19 vs server 1.12.4 minor drift (from Stage 5.3a) — still open.
  - `neo4j>=5.26` needs adding to `.env.example` and Colossus `.oh-venv` install docs (next slice).


## 2026-08-06 — consult_memory OpenHands tool + BFF emit-consultation endpoint (Stage 5.6b)
- **Source URL:** n/a — hand-authored, no upstream donor.
- **Kind:** hand-authored (no-port)
- **Location(s):**
  - `openhands_tools_ext/memory/tools/__init__.py` (new package marker)
  - `openhands_tools_ext/memory/tools/consult_memory.py` (~340 lines)
  - `bff/routers/memory.py` (extended: POST `/api/memory/emit-consultation`)
  - `scripts/forge-up.sh` (agent-server launched with `--import-modules openhands_tools_ext.memory.tools.consult_memory`)
- **Why hand-authored (donor check):** OpenHands SDK v1.40.0 ships builtin tools (`FinishTool`, `ThinkTool`) as reference templates. Both were inspected directly at `~/dev/forge-oh/.oh-venv/lib/python3.12/site-packages/openhands/sdk/tool/builtins/` before writing this tool; the file structure and `create()`/`ToolExecutor` idioms mirror those templates deliberately. No OSS component implements a Forge-OH-specific memory-tier query tool wired to the local `MemoryPort` composition, so nothing is vendored — only the SDK API is consumed.
- **License / ownership:** OpenHands SDK is MIT (transitively consumed as a pip dep). New Forge-OH code is same-owner (rmholston420).
- **Bridge design (ADR-024 D6 follow-through):** the tool runs inside the agent-server (:8090) which cannot invoke `bff.services.event_relay._emit` in-process, so `consult_memory` best-effort HTTP-POSTs the same wire fields to `POST /api/memory/emit-consultation` on the BFF (:8081), which in turn calls the existing library-only `emit_memory_consultation`. Tool result never fails on emit errors.
- **Verification:**
  - `openhands_tools_ext/tests/memory/test_consult_memory_tool.py` — happy path, unsupported tiers, empty results, emit-on-success + emit-on-failure + missing-conversation-id, registration lookup via `resolve_tool`.
  - `bff/tests/test_memory_emit_endpoint.py` — 503 gate, 200 wire shape, 422 validation cases, Socket.IO-failure resilience.
  - `src/tests/e2e/memory-timeline-marker.spec.ts` — creates a real run via ap-1 preset, POSTs the emit endpoint, asserts the 🧠 EventCard appears with the expected summary on the run-detail timeline, auto-pushes `screenshots/memory-timeline-marker.png`.
