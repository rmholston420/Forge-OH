# ADR-022 — Stage 5.4 zero-trust write enforcement satisfied by ported port-layer validators

**Status:** Ratified
**Lock-in phase:** Stage 5.4
**Supersedes:** —
**References:** ADR-021 (Consequences §Stage 5.4), Kosmos ADR-026, Kosmos ADR-027,
`openhands_tools_ext/memory/ports/memory.py`, `openhands_tools_ext/memory/ports/vector.py`,
`Forge-OH-reconciliation-plan-v1-stage-5.md` §5.4

## Context

The Forge-OH reconciliation plan §5.4 asks for a new pydantic
`MemoryWriteEvent` model that enforces two zero-trust invariants on every
memory write:

- `provenance` is required and non-empty
- `confidence` is a float in `[0.0, 1.0]`

The plan then asks that this validation be non-bypassable — every
adapter's `write_event()` / `upsert()` call site must construct the model
before persisting.

Stage 5.3b (commit `64ecab7` on `main`) already landed the Kosmos
`MemoryPort` and `VectorPort` layers, both of which include functionally
equivalent zero-trust validators enforced non-bypassably at the adapter
call sites:

- `openhands_tools_ext/memory/ports/memory.py::validate_zero_trust_write`
- `openhands_tools_ext/memory/ports/vector.py::validate_zero_trust_payload`

These validators are *strictly stronger* than the plan's proposed
`MemoryWriteEvent`:

| Rule | Plan's `MemoryWriteEvent` | Forge-OH port layer |
| --- | --- | --- |
| non-empty string `provenance` | ✅ | ✅ |
| `confidence` numeric | ✅ (pydantic coerces) | ✅ (strict, no coercion) |
| `confidence` in `[0.0, 1.0]` | ✅ | ✅ |
| reject `bool` as `confidence` | ❌ (pydantic accepts `True`/`False` as `1.0`/`0.0`) | ✅ (per Kosmos ADR-026) |
| reject non-`Real` types | ❌ (pydantic coerces strings) | ✅ |
| enforced at every live call site | proposed | ✅ live now (see §Rationale) |

The existing validators are already invoked at every write path:

- `DozerDbMemoryAdapter.write_event` — adapter.py:366
- `DozerDbMemoryAdapter.link_entities` — adapter.py:455
- `DozerDbMemoryAdapter.quarantine_write` — adapter.py:489
- `QdrantVectorAdapter.upsert` — qdrant/adapter.py:277
- `SemanticMemoryPath.embed_and_upsert` — inherits Qdrant validator on
  every upsert.

The Stage 5.3b contract suite (`bff/tests/memory/`, 96 passed / 1 skipped)
already covers every negative case the plan enumerates and several
stricter ones (bool-confidence rejection, non-numeric rejection,
boundary acceptance).

## Decision

**Stage 5.4 is satisfied by the port-layer validators landed in Stage 5.3b.**
Do NOT build the plan's proposed pydantic `MemoryWriteEvent` model.
Stage 5.4 closes with:

1. A verification script (`scripts/verify_stage_5_4_zero_trust.py`) that
   runs the plan §5.4.3 negative tests against the existing validators
   *and* against the live `DozerDbMemoryAdapter.write_event` call site.
2. A BUILD_LOG closure entry.
3. This ADR.

## Rationale

Two alternatives were considered:

**Alternative A — Ship `MemoryWriteEvent` as a wrapper.**
A pydantic model that delegates to `validate_zero_trust_write` /
`validate_zero_trust_payload` would give call sites the plan-specified
type surface without loosening enforcement. Rejected because:
- adds pydantic to `openhands_tools_ext.memory.ports.*` (currently zero
  pydantic deps in the port surface — pydantic lives only in the BFF
  request layer);
- duplicates every existing rejection test as a pydantic ValidationError
  variant;
- requires editing every adapter write-path already covered by port-layer
  guards, in exchange for zero behavior change.

**Alternative B — Ship `MemoryWriteEvent` as a replacement.**
Swap the port-layer functions for the pydantic model. Rejected because
pydantic v2 coerces `bool` → `float` and coerces numeric strings to
floats, which would silently *loosen* the ADR-026 rule that Kosmos
already carries.

Adopting the existing port-layer validators (this ADR) preserves the
ADR-026 stricter-than-plan behavior, avoids fanning pydantic into the
port surface, and reuses 20+ existing contract-test negative cases.

## Consequences

- `openhands_tools_ext/memory/ports/memory.py::validate_zero_trust_write`
  and `openhands_tools_ext/memory/ports/vector.py::validate_zero_trust_payload`
  are the canonical Forge-OH zero-trust write validators. Any new
  `MemoryPort` or `VectorPort` adapter (future backends) MUST call the
  matching validator on the first line of every write method.
- `scripts/verify_stage_5_4_zero_trust.py` is the Stage 5.4 DoD verifier
  and MUST stay green. Any change to the port-layer validator behavior
  or the adapter call-site enforcement is a Stage 5.4 regression until
  this script is updated with the new expectations.
- Stage 5.5 (ACE-style memory curation) can rely on the invariant that
  any `MemoryEvent` reaching the graph has already passed the zero-trust
  floor. Curation logic does not need to re-check `provenance` /
  `confidence` on read.
- No pydantic dependency is added to the port layer.
- `Forge-OH-reconciliation-plan-v1-stage-5.md` §5.4.2's proposed
  `MemoryWriteEvent` code block is superseded by this ADR. The plan
  document is not edited (per project policy — plans are inputs to ADRs,
  not synced downstream).

## Lock-in phase

This ADR is ratified at Stage 5.4 close and locks in the zero-trust
enforcement contract for all subsequent Stage 5 sub-stages.

## References

- ADR-021 (Consequences §Stage 5.4) — flagged Stage 5.4 satisfaction path.
- Kosmos ADR-026 — bool-as-confidence rejection rule.
- Kosmos ADR-027 — MemoryPort zero-trust write contract.
- `openhands_tools_ext/memory/ports/memory.py` lines 74–113 —
  `validate_zero_trust_write`.
- `openhands_tools_ext/memory/ports/vector.py` lines 93–126 —
  `validate_zero_trust_payload`.
- `openhands_tools_ext/memory/adapters/dozerdb/adapter.py` lines 366,
  455, 489 — DozerDB write call sites.
- `openhands_tools_ext/memory/adapters/vector/qdrant/adapter.py` line
  277 — Qdrant upsert call site.
- `bff/tests/memory/test_dozerdb_memory_adapter_contract.py` —
  `test_validate_rejects_*`, `test_validate_accepts_boundary_*`,
  `test_write_event_rejects_*` (17 tests).
- `bff/tests/memory/test_qdrant_adapter_contract.py` —
  `test_validate_zero_trust_payload_*`, `test_upsert_rejects_payload_*`
  (9 tests).
- `scripts/verify_stage_5_4_zero_trust.py` — Stage 5.4 DoD verifier
  (12 checks, all passing on 2026-08-06).
