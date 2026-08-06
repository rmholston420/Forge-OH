# ADR-023 — ACE-style memory curation cycle (Stage 5.5)

**Status:** Ratified
**Lock-in phase:** Stage 5.5
**Supersedes:** —
**References:** ADR-021 (`:MemoryEvent` triple shape), ADR-022 (zero-trust
write validators), Kosmos ADR-027 (MemoryPort contract),
`Forge-OH-reconciliation-plan-v1-stage-5.md` §5.5, ACA-v8 (ACE description).

## Context

The Forge-OH reconciliation plan §5.5 calls for an ACE-style
(generate → reflect → curate) cycle over memory writes, deduplicating
identical observations before they reach the `:MemoryEvent` graph.
The plan's code sketch was written against a proposed
`MemoryWriteEvent` pydantic surface (superseded by ADR-022) with a
free-string `content` field, and against a `search_semantic` /
`write_event` module-level function surface that does not exist in
Forge-OH.

Forge-OH's actual surface after Stage 5.3b:

- `:MemoryEvent` is **triple-shaped** (`subject`, `predicate`,
  `object`) per ADR-021 §D1.
- `MemoryPort.write_event(subject, predicate, object, *, provenance,
  confidence, ...)` is the canonical write entry.
- `MemoryPort.search_semantic(query, *, corpus, limit, min_score)` is
  an instance method on the adapter.
- The port-layer zero-trust validators (ADR-022) run as the first line
  of `write_event` and are strictly stricter than the plan's proposed
  pydantic validation (reject `bool` and non-`Real` confidence).

The plan's sketch also proposed replacing "any direct `write_event()`
calls from higher up the stack" with the cycle, but Forge-OH has no
higher-stack callers yet — Letta-style memory blocks (plan §5.5.4
note) are not built. There is nothing to wire in.

## Decision

Ship a **triple-shaped, deterministic, library-only** ACE cycle at
`openhands_tools_ext/memory/curation/ace_cycle.py` with:

- **D1** — Cycle input/output is triple-shaped (`CurationCandidate`
  carries `subject`/`predicate`/`object`), matching ADR-021's
  `:MemoryEvent`. Free-string observations must be lifted to a triple
  by the caller. The plan's free-string sketch is superseded.
- **D2** — Reflection is deterministic string-overlap over the
  normalized triple text (`f"{subject} {predicate} {object}"`,
  lowercase, whitespace-collapsed). No LLM call. No embedding
  similarity call. Escalation policy is spelled out in D5.
- **D3** — `curated_write` never swallows the port-level
  `ValueError` from `validate_zero_trust_write`. The zero-trust floor
  from ADR-022 remains authoritative; curation sits above it, not
  around it.
- **D4** — Reflection dispatch is substring-keyed on the reflection
  string (`"duplicate"` → discard, `"refine"` → merge, else → keep),
  so future escalations (D5) are drop-in — they only change what
  string is returned, not the dispatch.
- **D5** — Escalation path if deterministic string-overlap proves
  insufficient in practice:
  1. **First escalation** — embedding-similarity dedup via the
     already-ported `EmbeddingsPort` (call `adapter.search_semantic`
     with a low `min_score` and threshold on the returned similarity).
     Requires an ADR-023 amendment before landing.
  2. **Second escalation** — LLM-based reflection. Requires a fresh
     ADR (not an amendment) because it introduces a new cost/latency
     class and a new failure mode (LLM outage → write path degraded).
- **D6** — `merge` semantics beyond persistence (i.e., what "refine"
  should actually do to the existing event — supersede, update
  attributes, produce a delta edge, etc.) are **deferred** to a future
  ADR. This stage returns `merge` for near-misses but persists the
  candidate as a fresh `:MemoryEvent`, same as `keep`. The `merge`
  vs. `keep` distinction exists in the result object for downstream
  observers.
- **D7** — Library-only. No wire-in from higher-stack callers this
  stage. When a caller lands (Letta-style memory-block edits, ACE
  agent loop, etc.) it will import `curated_write` explicitly. This
  ADR pins the invariant: any future "standard write path" that
  wraps `write_event` MUST route through `curated_write`.

## Rationale

**Alternative A — Free-string surface (plan sketch literal).** Keep
`content: str` at the cycle boundary, synthesize a triple internally
(e.g., `subject="observation", predicate="STATES", object=content`).
Rejected because it breaks ADR-021's search invariants: the
`memory_event_text` FULLTEXT index is scored per-field, and shoving
every observation into `object` collapses the field structure.
Callers who genuinely have unstructured strings can lift them locally
with the synthetic-triple trick; the cycle should not bless that
loss.

**Alternative B — Ship embedding-similarity dedup now.** Reflection
calls `search_semantic` anyway (D1's related-memories lookup uses
the semantic lane); reuse the similarity score to dedup by threshold
instead of by string overlap. Rejected because we have no data on the
right threshold. The plan says explicitly: "escalate to
embedding-similarity-based duplicate detection only if deterministic
string-overlap proves insufficient in practice; do not add an LLM
call for this without evaluation evidence justifying it." String
overlap is strictly cheaper and its false-positive/false-negative
profile is trivially inspectable. Locking a threshold without
evidence would be premature.

**Alternative C — Wire the cycle into `adapter.write_event`
automatically** (make every write curated). Rejected because ADR-021
D5 (NoOpAmgPolicy) already runs adapter-level policy layers; making
curation implicit at the adapter layer would blur the port contract
(callers get silent discards). Library-only preserves the invariant
that "if you called `write_event`, we tried to persist."

## Consequences

- **New module** `openhands_tools_ext/memory/curation/` with
  `ace_cycle.py` (~275 lines) and `__init__.py` re-exporting the
  public surface. No pydantic dependency.
- **New contract tests** `bff/tests/memory/test_ace_curation_contract.py`
  (15 tests) covering candidate shape, reflection semantics, `curate`
  dispatch, orchestrator persistence, and zero-trust preservation.
  Full memory suite grows 96 → **111 passed, 1 skipped** under both
  baseline and `OLLAMA_EMBED_MODEL=qwen3-embedding:4b`.
- **New DoD verifier** `scripts/verify_stage_5_5_curation.py`
  (3 checks). Runs standalone with `PYTHONPATH=.` — no live infra.
- **No changes** to `MemoryPort`, `VectorPort`, `EmbeddingsPort`,
  their adapters, or the port-layer zero-trust validators.
- **Deferred to future ADRs:** embedding-similarity escalation (D5.1),
  LLM-reflection escalation (D5.2), `merge`/`supersede` semantics
  (D6), wire-in to higher-stack callers (D7).
- **`Forge-OH-reconciliation-plan-v1-stage-5.md` §5.5.1 and §5.5.2**
  code sketches are superseded by this ADR + the shipped module.
  The plan document is not edited (plans are inputs to ADRs, not
  synced downstream).

## Lock-in phase

Ratified at Stage 5.5 close. Locks in the cycle shape (triple, three
actions, substring dispatch), the zero-trust floor invariant (D3),
the escalation policy (D5), and the library-only invariant (D7) for
all subsequent Stage 5 sub-stages.

## References

- ADR-021 §D1 — `:MemoryEvent` triple shape.
- ADR-022 — port-layer zero-trust validators.
- Kosmos ADR-026 — bool-as-confidence rejection (relevant because D3
  requires that guard remain non-bypassable).
- Kosmos ADR-027 — MemoryPort contract.
- `openhands_tools_ext/memory/curation/ace_cycle.py` — cycle
  implementation.
- `openhands_tools_ext/memory/curation/__init__.py` — public surface.
- `bff/tests/memory/test_ace_curation_contract.py` — 15 contract tests.
- `scripts/verify_stage_5_5_curation.py` — Stage 5.5 DoD verifier.
- `Forge-OH-reconciliation-plan-v1-stage-5.md` §5.5.
