# Forge-OH — Session Handoff

**Last update:** 2026-08-06 02:17 EDT

## Current build-sequencing stage
Stage 5.3b — **DozerDB MemoryPort adapter scope frozen**, awaiting user sign-off before port begins.

## Stage 5.3a — CLOSED
- Sandbox verification: 54 passed / 1 skipped (both baseline and 4B A/B)
- Colossus live-tier verification: PASSED
- `search_semantic('smoke', corpus='default')` returns `[]` cleanly against live Qdrant

## Stage 5.3b — FROZEN SCOPE (see BUILD_LOG entry above)

**Files to port from Kosmos @ `c455165`:**
1. `adapters/memory/dozerdb/adapter.py` (552 lines) — `DozerDbMemoryAdapter` + `TemporalIndex` Protocol + `InMemoryTemporalIndex` + `GraphBackend` Protocol + `InMemoryGraphBackend`
2. `adapters/memory/dozerdb/dozerdb_graph_backend.py` (215 lines) — real Bolt driver, takes uri/user/password/database as ctor args (no env-var coupling)
3. `adapters/memory/dozerdb/amg_policy.py` (218 lines) — `AmgGuardPolicy` wrapping `agent_memory_guard==0.3.0`
4. `adapters/memory/dozerdb/amg_v02_policy.py` (16 lines) — one-release-cycle backward-compat alias
5. `adapters/memory/dozerdb/test_contract.py` (442 lines) — full contract suite

**Deps to add to `.oh-venv`:**
- `neo4j>=5.26` (Bolt driver)
- `agent-memory-guard==0.3.0` (write-time policy filter, PyPI, license TBD-verify)

**Kosmos code changes needed (mechanical):**
- Import path rewrites: `from ports.*` → `from openhands_tools_ext.memory.ports.*`; `from .semantic_memory_path` → keep (relative)
- Docstring cleanup: remove stale Graphiti references in `adapter.py` (lines 8, 20, 23, 221, 303, 309-310) — replace with post-ADR-075 wording
- Wiring: remove `GraphitiTemporalIndex` import from smoke.py, replace with either `InMemoryTemporalIndex` (simple) or new plain-Cypher DozerDB-backed `TemporalIndex` (durable but new code)

**Namespace decision (ADR-019 Option A):** node label `MemoryEvent` distinct from RepoGraph's `Symbol`. All memory writes go through `DozerDbGraphBackend(database="forgeoh")`. Both surfaces coexist in the `forgeoh` database.

**Composition-root wiring (Forge-OH-side, NEW code):**
- New `openhands_tools_ext/memory/composition.py` (~40 lines) — reads `NEO4J_BOLT_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`/`NEO4J_DATABASE` + Ollama + Qdrant env vars, wires `DozerDbMemoryAdapter(graph=..., amg=..., temporal=..., embeddings=..., vector=...)`

**Stop condition for 5.3b:**
1. All ported contract tests green (in-memory backends, no live services required)
2. Round-trip live smoke: `write_event(subject="Colossus", predicate="hasComponent", object="RTX 5090", provenance="stage-5.3b-smoke", confidence=0.95)` → `search_semantic("Colossus")` returns 1 hit with the same payload; `query_temporal("Colossus")` returns the same event
3. RepoGraph regression: existing `Symbol` label queries still work — no collision in `forgeoh` DB

## Three OPEN DECISIONS awaiting user answer before I touch the repo

1. **`TemporalIndex` implementation for production:**
   - **1a.** `InMemoryTemporalIndex` (fastest — the only concrete impl Kosmos ships) — process-restart erases temporal state. Fine for Stage 5.3b's smoke, but a follow-up ADR must decide durable temporal storage before Stage 5.5 curation.
   - **1b.** Write a new plain-Cypher `DozerDbTemporalIndex` right now — durable, no restart loss, but ~150 new lines of code and a new small ADR to file.
   - **1c.** Defer temporal surface entirely by using a no-op stub — Stage 5.3b would then NOT satisfy `query_temporal` in the round-trip smoke; only semantic-lookup is proved live.
   - **My recommendation:** **1a** — smallest scope, matches Kosmos exactly, unblocks 5.4. File a new ADR-021 (Forge-OH-side) declaring "`TemporalIndex` durability deferred to Stage 5.5" so the choice is documented.

2. **`agent-memory-guard` v0.3.0 adoption:**
   - **2a.** Port `AmgGuardPolicy` verbatim + pull `agent-memory-guard` from PyPI — matches Kosmos exactly.
   - **2b.** Use Kosmos's `NoOpAmgPolicy` (`amg_policy.py` also ships an always-allow variant used in tests) — no PyPI dep pulled, all writes allowed unconditionally. Simpler for a single-user local system; can be swapped later.
   - **2c.** Use `AlwaysBlockAmgPolicy` (also in Kosmos) — hard-fails all writes, useful for smoke-tests only.
   - **My recommendation:** **2b (NoOpAmgPolicy)** — you're single-user local; the zero-trust port-level guard (`validate_zero_trust_write`) already enforces the essential invariant (provenance + confidence required). `agent-memory-guard` is designed for multi-agent PII redaction, which does not apply here. Skip the PyPI dep. Revisit only if plugin ecosystem expands.

3. **Kosmos docstring drift in `adapter.py`:**
   - **3a.** Port the docstrings verbatim (stale but harmless — just says "Graphiti in prod" when the file that was Graphiti has been deleted).
   - **3b.** Clean up the docstrings at port time to say "Uses `InMemoryTemporalIndex` in Forge-OH (see ADR-021)" — cleaner but slightly non-verbatim.
   - **My recommendation:** **3b** — porting stale docstrings verbatim is a slow-motion bug. Log the docstring cleanup explicitly in PORTING_LEDGER.

## Exact next action
Wait for user sign-off on the three OPEN DECISIONS above, then execute Stage 5.3b port with the chosen options.

## Prior deviation still relevant (5.4 gotcha)
Kosmos ports already ship `validate_zero_trust_write()` (`ports/memory.py`) and `validate_zero_trust_payload()` (`ports/vector.py`). Plan §5.4's proposed pydantic `MemoryWriteEvent` is **redundant** — use verbatim Kosmos helpers when §5.4 begins.

## Env-var contract (Forge-OH final naming)
- `NEO4J_BOLT_URI` (Forge-OH) NOT `NEO4J_URI` (Kosmos) — set at composition root, Kosmos adapter code takes `uri` as ctor arg with zero env coupling so this is Forge-OH-side only
- `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE=forgeoh` — identical between projects
- `OLLAMA_URL` (native root, embeddings) vs `OLLAMA_BASE_URL` (OpenAI-compat, chat) — NOT interchangeable
- `QDRANT_URL` — default `http://localhost:6333` for both
