# ADR-021 — Memory adapter graph shape: CIDOC-native triples + MemoryEvent node + fulltext temporal index

**Status:** Ratified
**Lock-in phase:** Stage 5.3b
**Supersedes:** —

> **STATUS AMENDMENT (2026-08-06 02:31 EDT):** D1 amended to match Kosmos's actual `write_event` graph shape after re-inspecting `adapter.py` lines 394–412 at pinned SHA `c455165`. Kosmos already implements a CIDOC-star topology (event as center, entities as spokes) that satisfies the A2 + α intent — no code rewrite needed. Original draft (a hand-designed `(:Subject)-[:PREDICATE]->(:Object)` direct edge plus `[:HAS_SUBJECT]`/`[:HAS_OBJECT]`) was strictly worse: it required Cypher label injection for subject/object names, and the direct predicate edge was redundant with the star topology. Amendment adopts Kosmos's shape verbatim: `:Entity` label (role-property-tagged) + `[:SUBJECT_OF]`/`[:OBJECT_OF]` from event to entities. This preserves the CIDOC-native semantic (event is a proper reified relationship, addressable and queryable) and eliminates all A2-specific write-path porting work — Kosmos's `write_event` becomes portable verbatim.

## Context

Stage 5.3b ports Kosmos's `DozerDbMemoryAdapter` (ADR-027 + ADR-074 §D3) into Forge-OH. Kosmos ships the port with three concrete implementations of the composed Protocol seams:

- `GraphBackend` → `DozerDbGraphBackend` (real Bolt driver)
- `AmgPolicy` → `AmgGuardPolicy` (wraps `agent-memory-guard==0.3.0`)
- `TemporalIndex` → **DELETED** by Kosmos ADR-075 D1 (Graphiti hard-deleted). Only `InMemoryTemporalIndex` remains.

Forge-OH must supply a durable `TemporalIndex` because Stage 5.5's ACE curation cycle and Stage 5.6's Memory Inspector UI both require temporal queries to survive process restarts. Additionally, the shape of graph writes and the storage of temporal facts is a decision surface Kosmos left implicit — its `write_event` decomposes payloads into `subject/predicate/object` internally but its `TemporalIndex.record_event` receives an opaque `payload` dict rather than a graph shape.

Colossus-side infrastructure (confirmed 2026-08-06 02:14 EDT):

- `kosmos-dozerdb` (`graphstack/dozerdb:5.26.27`) running with 190 APOC procs, zero Graphiti procs, `forgeoh` database online (ADR-019 Option A shared instance)
- Env: `NEO4J_BOLT_URI=bolt://localhost:7687`, `NEO4J_USER=neo4j`, `NEO4J_DATABASE=forgeoh`
- RepoGraph already writes `Symbol`/`File` labels into `forgeoh`; a distinct namespace is required to avoid collision

## Decision

Adopt the **A2 + B2 + C1 + α + δ** graph shape for the Forge-OH memory adapter's `DozerDbTemporalIndex`:

### D1 — Storage model: CIDOC-native reified-event triples via Kosmos's shape (A2 + α, amended)

Every `MemoryPort.write_event` call produces the following structure in the `forgeoh` database, using Kosmos's existing `write_event` implementation (`adapters/memory/dozerdb/adapter.py` lines 394–412) unchanged:

```
(:Entity {value: <subject>, role: "subject"})                          (CREATE — subject entity)
(:Entity {value: <object>,  role: "object"})                           (CREATE — object entity)

(:MemoryEvent {                                                        (CREATE — event is the reified relationship)
    id: <uuid>,                                                        (primary key; same string SemanticMemoryPath uses)
    predicate: <str>,                                                  (CIDOC-CRM predicate name)
    subject: <str>,
    object: <str>,
    written_at: <ISO-8601 str>,                                        (= as_of; Kosmos names it written_at internally)
    provenance: <str>,
    confidence: <float>,
    pii_tier: <str>,
    source_citation: <str|null>,
    attributes: <json str>                                             (sanitized by _sanitize_props in graph backend)
})

(:MemoryEvent)-[:SUBJECT_OF {role: "subject"}]->(:Entity)
(:MemoryEvent)-[:OBJECT_OF  {role: "object"}]->(:Entity)
```

Properties of this shape:

- **Reified event.** The `:MemoryEvent` node IS the triple. This is the CIDOC-CRM "event-as-object" pattern in its canonical form — the relationship between subject and object is a first-class addressable entity with its own properties, not an anonymous edge.
- **Star topology, not direct edge.** There is deliberately NO direct `(:Entity)-[:PREDICATE]->(:Entity)` edge between subject and object. All traversal from subject to object goes through the event node. This is correct for a temporal/provenanced knowledge graph: the same subject/object may be linked by many events (different times, different provenances, different confidences), and a single flat edge cannot express that.
- **Predicate name is a property.** Stored on `:MemoryEvent.predicate` (a string), not encoded into a Cypher relationship type. This eliminates the Cypher-label-injection surface that `DozerDbGraphBackend._validate_identifier` guards against for `SUBJECT_OF`/`OBJECT_OF`.
- **`id` as primary key.** The same UUID used by `SemanticMemoryPath` as the vector-store point id (ADR-074 D3 invariant 4). Vector-store hits resolve to `MemoryEvent` nodes via `MATCH (n:MemoryEvent {id: $event_id}) RETURN n`.
- **Zero deviation from Kosmos.** No graph-write code changes required; the shape is exactly what Kosmos's `write_event` already produces at pinned SHA `c455165`.

Callers who want type-filtered temporal queries write:

```cypher
MATCH (e:MemoryEvent {predicate: 'hasComponent'})-[:SUBJECT_OF]->(subject:Entity {value: 'Colossus'})
MATCH (e)-[:OBJECT_OF]->(object:Entity)
RETURN e, subject.value, object.value
ORDER BY e.written_at DESC
```

### D2 — Fulltext temporal index (B2)

On adapter first-boot, `DozerDbTemporalIndex.ensure_indexes()` creates:

```cypher
CREATE FULLTEXT INDEX memory_event_text IF NOT EXISTS
    FOR (n:MemoryEvent) ON EACH [n.subject, n.predicate, n.object, n.source_citation];
CREATE RANGE INDEX memory_event_written_at IF NOT EXISTS
    FOR (n:MemoryEvent) ON (n.written_at);
CREATE CONSTRAINT memory_event_id_unique IF NOT EXISTS
    FOR (n:MemoryEvent) REQUIRE n.id IS UNIQUE;
```

`query_temporal(query, as_of=None, limit=20)` executes:

```cypher
CALL db.index.fulltext.queryNodes('memory_event_text', $query) YIELD node, score
WHERE $as_of IS NULL OR node.written_at <= $as_of_iso
RETURN node, score
ORDER BY score DESC, node.written_at DESC
LIMIT $limit
```

`written_at` is stored as an ISO-8601 string (matching Kosmos's `_sanitize_props` output) rather than a Neo4j `datetime()`. String comparison on ISO-8601 timestamps is correct for lex-ordered chronological comparison. The `_written_at` range index still accelerates the WHERE clause.

Lucene provides the `score` field of `MemoryHit`. When `query` is empty the method returns `[]` immediately without touching the index.

### D3 — Single-timestamp semantic (C1)

`written_at` is the only temporal axis (Kosmos's naming; corresponds to `as_of` in the `TemporalIndex` Protocol signature). It records when the fact was written to the memory graph. `write_event` sets it to `datetime.now(timezone.utc)` at the moment of the write. `query_temporal(as_of=T)` returns events with `written_at <= T`, matching `InMemoryTemporalIndex.query_temporal` line 274.

Valid-time / transaction-time bitemporal separation is explicitly deferred. When it lands, an additive migration is possible without breaking the current contract: add a nullable `valid_time` property and a second parameter to `query_temporal`. This ADR reserves that migration path.

### D4 — Vector-store payload unchanged (δ)

`SemanticMemoryPath.embed_and_upsert` continues to persist the same flat payload it persists today (subject / predicate / object / provenance / confidence / pii_tier / source_citation / attributes / event_id / corpus / as_of). Graph node/edge IDs are NOT written into the vector-store payload. Callers who receive a `MemoryHit` from `search_semantic` and want to graph-walk resolve `event_id` to the `MemoryEvent` node via a single Cypher hop.

Rationale: adding graph internal IDs to the vector-store payload creates unwanted coupling between VectorPort and DozerDB internals, and provides no meaningful savings — the round-trip cost is one indexed node lookup.

### D5 — AmgPolicy: `NoOpAmgPolicy` in production (2b sub-decision)

The ported `DozerDbMemoryAdapter` composition root wires Kosmos's `NoOpAmgPolicy` (already shipped in Kosmos's `adapter.py`). `agent-memory-guard==0.3.0` is NOT pulled as a dependency in Stage 5.3b.

Rationale: Forge-OH is a single-user local-first system per the space contract. `agent-memory-guard` targets multi-agent PII redaction, which does not apply. The zero-trust invariants (provenance and confidence required on every write) are still enforced non-bypassably at the `ports.memory.validate_zero_trust_write` layer. AMG can be swapped in later if the plugin ecosystem expands to multi-agent scenarios; the seam is preserved.

## Rationale

**Why A2 over A1 (flat single-node storage):** A1 would store each event as a single `:MemoryEvent` node with subject/predicate/object as properties and no explicit graph edges. It's simpler but forfeits the graph-native query surface that RepoGraph and future Gnosis-style knowledge queries require. A2 costs 3 additional writes per event (2 nodes MERGE'd, 3 rels) — cheap on a single-user workstation, and DozerDB's write throughput comfortably absorbs it.

**Why B2 over B1 (CONTAINS on stringified payload):** Kosmos's `InMemoryTemporalIndex.query_temporal` uses `str(payload).lower()` `CONTAINS` for text search — a test-tier shortcut. Production users deserve real relevance scoring. Lucene fulltext via `db.index.fulltext.queryNodes` is a 1-line index creation and a 1-line query; the code overhead vs `CONTAINS` is trivial and the UX difference is enormous.

**Why C1 over C2 (bitemporal):** C2 would fork `MemoryPort`'s contract from Kosmos (needs two-timestamp `write_event` and `query_temporal` signatures) and require re-scoping Stage 5.4 and 5.5. Additive path to bitemporal remains open under C1.

**Why α over β (dedicated MemoryEvent node):** β puts fulltext on `:Subject`/`:Object` nodes — those are shared across many events, making fulltext hits noisy and requiring post-filtering by `as_of`. α puts fulltext on a per-event node, giving one-to-one hit-to-event semantics.

**Why δ over ε (no graph IDs in vector payload):** ε bakes graph implementation details (`node_id`, `edge_id`) into the vector-store payload. That crosses a port-boundary Kosmos deliberately preserved (VectorPort knows nothing about graph adapters). One extra Cypher hop is the correct price for that separation.

## Consequences

**Files created:**
- `openhands_tools_ext/memory/adapters/dozerdb/dozerdb_temporal_index.py` (~200 lines, new Forge-OH code)
- Contract test for the above
- `openhands_tools_ext/memory/composition.py` (~50 lines, Forge-OH composition root that reads `NEO4J_BOLT_URI` etc. and wires the adapter)

**Files ported from Kosmos @ `c455165` (import rewrites + docstring cleanup only — no shape/write-path rewrites needed after D1 amendment):**
- `adapters/memory/dozerdb/adapter.py` (552 lines) → `openhands_tools_ext/memory/adapters/dozerdb/adapter.py`
- `adapters/memory/dozerdb/dozerdb_graph_backend.py` (215 lines) → same relative path
- `adapters/memory/dozerdb/amg_policy.py` (218 lines) → same relative path — only `NoOpAmgPolicy` referenced at composition root; `AmgGuardPolicy` retained but not wired
- `adapters/memory/dozerdb/amg_v02_policy.py` (16 lines) → same relative path — backward-compat alias
- `adapters/memory/dozerdb/test_contract.py` (442 lines) → `bff/tests/memory/test_dozerdb_memory_adapter_contract.py`

**Dependencies added:**
- `neo4j>=5.26` in `.env.example` / documentation. Installed on Colossus via `pip install neo4j>=5.26` into `.oh-venv`.

**Dependencies NOT added:**
- `agent-memory-guard` (deferred; `NoOpAmgPolicy` used in composition root)
- `graphiti-core` (Kosmos ADR-075 D1 hard-deleted this; Forge-OH inherits)

**PORTING_LEDGER.md:** new entry for Stage 5.3b marking the four ported files and the two new Forge-OH-side files. Graphiti is NOT ledgered because we never ported it.

**Downstream ADRs affected:**
- Stage 5.4 (zero-trust write enforcement) — inherits the A2 graph shape; the `validate_zero_trust_write` port-level guard runs before any graph write in this ADR's write path
- Stage 5.5 (curation cycle) — will query `MemoryEvent` nodes via the fulltext index defined in D2
- Stage 5.6 (Memory Inspector UI) — will render `MemoryEvent` nodes and their `[:HAS_SUBJECT]`/`[:HAS_OBJECT]` links

## Lock-in phase

Stage 5.3b completion on Colossus (round-trip smoke: write_event → search_semantic → query_temporal returns the same event via both surfaces).

## References

- ADR-019 (DozerDB shared instance, Option A) — this ADR uses the `forgeoh` database in the shared instance
- ADR-020 (Qwen3-Embedding default) — the embedder used by `SemanticMemoryPath`
- ADR-027 (Kosmos: MemoryPort + DozerDB + Graphiti + AMG) — the ported adapter's authority; D5 diverges (NoOpAmgPolicy)
- ADR-074 (Kosmos: semantic memory surface) — `SemanticMemoryPath` inherited; D4 confirms the payload contract
- ADR-075 D1 (Kosmos: Graphiti hard-delete) — this ADR replaces the deleted `TemporalIndex` with `DozerDbTemporalIndex`
- `PORTING_LEDGER.md` Stage 5.3b entry (to be filed alongside the port commit)
