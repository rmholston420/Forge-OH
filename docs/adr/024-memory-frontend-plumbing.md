# ADR-024 — Memory frontend plumbing (Stage 5.6a)

**Status:** Ratified
**Lock-in phase:** Stage 5.6 (Forge-OH-Action-Plan-v4 §5.6.1–§5.6.3)
**Supersedes:** —

## Context

Stage 5.6 in Forge-OH-Action-Plan-v4.md mandates a visible frontend surface
for the memory subsystem: the timeline must render a distinct marker for
memory consultations, and a dedicated "Memory" page must let the operator
inspect recent MemoryPort writes. The prior stages produced port + adapter
+ ACE curation (5.3 through 5.5) but nothing user-visible; a UI slice is a
plan-level DoD for 5.6.

Constraints:

- Local-first single-user (`Forge-OH` space instructions). No cloud
  control plane, no auth surface, no multi-tenant assumptions.
- Existing wire shape: `ToolEvent{ id, type, timestamp, source?, summary?, raw?, ... }`
  produced by `bff/services/event_normalize.normalize_event`. Frontend
  reads `event.type` as the discriminator (ADR-018).
- BFF is a passthrough to agent-server, but Stage 5.6 introduces a
  BFF-owned resource (recent memory writes) that has no upstream
  counterpart in agent-server; the BFF must talk to DozerDB directly for
  this endpoint.
- Neo4j password is optional at BFF boot (dev laptops, CI); the memory
  UI must degrade gracefully to a 503 + warning banner.
- 5.6b's live-task DoD (agent actually consults memory and emits an
  event) is deferred; 5.6a is the plumbing slice so the frontend can
  render the marker + inspector page from fixture data or manual pokes.

## Decision

The following are the load-bearing decisions ratified by this ADR.

**D1 — Ship frontend and backend together, not deferred.**
Stage 5.6 explicitly calls out the frontend surface as mandatory. We
ratify the visible-marker + inspector-page requirement here; deferring
the whole stage would leave the memory subsystem invisible in the UI
for another cycle. 5.6a introduces both sides; 5.6b later plugs in the
real caller (`consult_memory` tool + agent-server wiring).

**D2 — New event kind `MemoryConsultationEvent` → normalized type `memory_consultation`.**
Raw payload shape: `{ tier: str, query: str, result_count: int }` plus
the shared envelope (`id, kind, timestamp, source, runId`). The BFF
projector `normalize_event` maps `MemoryConsultationEvent` to type
`memory_consultation` and computes summary
`Memory consulted (<tier>): "<query>" — <n> result(s)` — see
`bff/services/event_normalize.py :: _memory_consultation_summary`.

**D3 — Add `list_recent_writes(*, limit)` to `MemoryPort`.**
The frontend inspector needs newest-first recent-write projection. We
add a formal port method (rather than reading DozerDB from the BFF
directly) so the surface stays adapter-agnostic and testable against
the in-memory backend. The Protocol change is safe: the only in-repo
implementer is `DozerDbMemoryAdapter`. Wire shape returned by
`bff/routers/memory.py` mirrors the dataclass fields verbatim (with
snake_case → camelCase for `piiTier / sourceCitation / writtenAt`).

**D4 — Inspector uses triple-shape display convention.**
Six-column table: Subject / Predicate / Object / Provenance / Confidence /
PII tier / Written. Matches the CIDOC-native shape locked in ADR-021.

**D5 — BFF MemoryPort singleton composed at startup (K1).**
`bff/deps/memory_port.py` lazily composes a single `DozerDbMemoryAdapter`
via `openhands_tools_ext.memory.composition.make_memory_adapter()`,
stored as a module-level singleton and torn down in the FastAPI
`lifespan`. Composition failures are non-fatal — the BFF still boots
without `NEO4J_PASSWORD` set; the memory router 503s and the frontend
renders a warning banner. Alternatives considered:

- K2: FastAPI dependency-injected factory per request → wasteful driver
  churn; rejected.
- K3: Reuse the existing `bff/deps/neo4j_driver.py` sync driver →
  wrong async surface for the DozerDB adapter; rejected.

**D6 — `emit_memory_consultation` is library-only until a caller exists.**
Mirrors ADR-023 D7 for curation. Provided so 5.6b can wire the real
tool without additional BFF work; unit-tested in `test_memory_events.py`.
Does not fire on any code path today.

**D7 — Playwright visual verification deferred to the user's Colossus
run** (per `forge-oh-playwright-visual`). Sandbox test coverage: 5
router tests + 12 pure-factory/normalizer tests + 4 React component
tests + 7 port contract tests (already green in 5.6a — see
`bff/tests/memory/test_list_recent_writes_contract.py`).

## Rationale

- **Formal port method** rather than a BFF-side Cypher query: keeps the
  adapter boundary honest and lets us satisfy the contract with the
  in-memory backend for tests.
- **Non-fatal composition** matters because Forge-OH devs (including
  CI) frequently boot the BFF without DozerDB; the memory feature must
  not gate the entire product.
- **Triple-shape table** is the smallest possible inspector that
  respects ADR-021's decision to store CIDOC triples on
  `:MemoryEvent`. Editing / expanding is out of scope.
- **Event-kind mapping** keeps the existing `event_normalize` pattern —
  discriminator on `kind`, produce a new `type` string, no new union
  type in Zod (only an `.or(z.string())` fallback is affected).

## Consequences

Files added/changed:

- `openhands_tools_ext/memory/ports/memory.py` — new
  `MemoryEventRecord` dataclass; new `list_recent_writes` on
  `MemoryPort`.
- `openhands_tools_ext/memory/adapters/dozerdb/adapter.py` — new
  `list_recent_writes` method (in-memory + DozerDB backends).
- `bff/services/event_normalize.py` — new
  `MemoryConsultationEvent → memory_consultation` mapping and
  `_memory_consultation_summary` helper.
- `bff/services/memory_events.py` — new emitter helper (library-only).
- `bff/deps/memory_port.py` — new lazy singleton for the BFF.
- `bff/routers/memory.py` — new `GET /api/memory/recent-writes` router.
- `bff/main.py` — router mount + lifespan close of the singleton.
- `src/lib/schemas/event.ts` — `memory_consultation` added to
  `EventTypeSchema` enum.
- `src/components/domain/EventCard.tsx` — brain icon for
  `memory_consultation`.
- `src/features/memory-inspector/` — new feature module (api / hooks /
  schemas / page).
- `src/app/(dashboard)/memory-inspector/page.tsx` — new route.
- `src/components/navigation/Sidebar.tsx` — new nav entry.
- `src/lib/query/query-keys.ts` — new `memoryKeys` block + export.
- Tests: `bff/tests/test_memory_router.py`, `bff/tests/test_memory_events.py`,
  additions to `bff/tests/test_event_normalize.py`,
  `src/tests/unit/MemoryInspectorPage.test.tsx`,
  `src/tests/unit/EventCard-memory.test.tsx`.

No PORTING_LEDGER changes (no external code adopted; the row layout and
graceful-503 approach are hand-authored to fit Forge-OH's local-first
posture).

## Lock-in phase

Stage 5.6a. 5.6b will add the `consult_memory` OpenHands tool and wire
it to `emit_memory_consultation` at the agent-server / tool layer,
completing the plan's live-task DoD for 5.6.

## References

- Forge-OH-Action-Plan-v4.md §5.6 (Frontend integration — mandatory)
- ADR-021 (memory adapter graph shape) — triple convention
- ADR-023 (ACE curation cycle) — library-only pattern precedent
- ADR-018 (Serena integration) — `event.type` string discriminator
  convention re-used here
- `bff/tests/memory/test_list_recent_writes_contract.py`
