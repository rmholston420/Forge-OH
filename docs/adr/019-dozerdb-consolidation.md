# ADR-019 — DozerDB consolidation: Kosmos-canonical shared instance

**Status:** Accepted
**Lock-in phase:** Stage 4.5 (Stage 4 exit gate; hard blocker for Stage 5)
**Supersedes:** —
**Related:** `docs/reconciliation-plan-stage-4.md § 4.5`, ADR-006 (RepoGraph — Tier 2 of the retrieval cascade), ADR-018 (Serena LSPClient — Tier 1), `PORTING_LEDGER.md` (Kosmos `ops/compose/memory.yml` reference entry)

## Context

The Forge-OH reconciliation plan (`docs/reconciliation-plan-stage-4.md § 4.5`) flags DozerDB consolidation as a "real architectural decision, not a mechanical task" that must be resolved before Stage 5's Kosmos-ported semantic-memory work begins. Two options are on the table:

- **Option A — single shared DozerDB instance.** Forge-OH RepoGraph and Kosmos memory plugins coexist in one DozerDB container, distinguished by database names or node labels.
- **Option B — two separate graph instances.** Each project runs its own DozerDB container.

The plan recommends A by default, but requires explicit facts and owner sign-off before proceeding.

### Facts gathered (2026-08-06 01:12 EDT)

Direct inspection of `github.com/rmholston420/kosmos` at HEAD and the current Forge-OH tree established:

- **Zero `dozer.*` procedure calls anywhere in Kosmos.** `grep -rn "dozer\." --include="*.py"` returned no hits. Kosmos accesses DozerDB exclusively through the stock `neo4j` async Python driver over Bolt. There is no DozerDB-fork-specific feature in play.
- **Kosmos owns the canonical DozerDB definition.** `ops/compose/memory.yml` in the Kosmos repo defines a container named `kosmos-dozerdb`, image `graphstack/dozerdb:5.26.27`, ports `7474:7474` + `7687:7687`, plugins `["apoc"]`, heap 2G initial / 4G max, pagecache 2G, healthcheck via `cypher-shell`. This is the same container currently running on Colossus.
- **Forge-OH's compose files do not define DozerDB.** `docker-compose.yml` and `docker-compose.dev.yml` in `rmholston420/Forge-OH` bring up `bff`, `openhands`, `frontend`, `caddy`, `redis` — no graph service. Forge-OH connects to whatever DozerDB is already listening on `bolt://127.0.0.1:7687`.
- **Database-per-workload isolation already in code.** ADR-006 established the `forgeoh` database name; `openhands_tools_ext/repograph/store.py` creates all constraints/indices under the `forgeoh_*` prefix; `bff/settings.py` defaults `neo4j_database = "forgeoh"`. Kosmos plugins currently use the default `neo4j` database; future Kosmos code is free to create additional named databases without colliding.
- **Live state on Colossus (2026-08-03 07:11 EDT, still current):** the Kosmos-spec `kosmos-dozerdb` container has `forgeoh` created inside it via `CREATE DATABASE forgeoh IF NOT EXISTS`, indexed to 547 File + 2150 Symbol nodes. The consolidation is already in effect operationally; this ADR only ratifies it.

### Why this is decision-worthy despite the operational reality

The reconciliation plan is right to require sign-off: an implicit shared instance that no ADR names is a foot-gun. Someone could later "fix" it by forking a second DozerDB container, or add DozerDB to Forge-OH's compose in the belief that Forge-OH should own its own graph store. Locking Option A explicitly names Kosmos as the canonical owner of the DozerDB definition and reserves the `forgeoh` database name.

## Decision

### D1 — Option A: single shared DozerDB instance, Kosmos-canonical

Ratify the current arrangement: **one `kosmos-dozerdb` container on Colossus, defined by Kosmos's `ops/compose/memory.yml`, shared by all local-first graph workloads on Colossus.** Isolation is provided by Neo4j database names, not container boundaries.

Corollaries:

1. **Forge-OH does not duplicate the DozerDB compose definition.** `docker-compose.yml` and `docker-compose.dev.yml` in Forge-OH remain graph-service-free. If a Forge-OH-only dev environment ever needs a standalone DozerDB (e.g., an isolated CI runner not co-located with Kosmos), it must launch the same image with the same tag and use a different container name — this ADR is the reference.
2. **Database name `forgeoh` is reserved for Forge-OH RepoGraph.** Any Kosmos plugin or future Forge-OH component that needs graph storage must pick a different database name.
3. **The Bolt endpoint contract is stable.** Forge-OH BFF settings default to `NEO4J_URI=bolt://127.0.0.1:7687`. Any change to that URI (e.g., swapping to `neo4j://` for routing, moving off `127.0.0.1`) requires a new ADR because it affects both projects.

### D2 — Cross-project startup ordering is a Kosmos concern

DozerDB is a shared local-first service on Colossus, so its lifecycle belongs to whoever owns the systemd/compose that starts it — currently the user, via manual `docker compose -f ops/compose/memory.yml up -d` from the Kosmos checkout. Forge-OH's `GET /api/repograph/health` already returns `available: false` when Bolt is unreachable; the BFF neither starts DozerDB nor waits for it. This ADR does not introduce a Forge-OH-owned service dependency on Kosmos code; it only points at the Kosmos compose file as the canonical spec.

### D3 — No shared-authentication story yet

The current password `kosmos-dev-password` (from Kosmos's `ops/compose/memory.yml`) is a dev-only single-user secret. Forge-OH's `.env.neo4j` currently holds a different password because DozerDB was rotated after initial provisioning; this ADR does not force a re-alignment. When the two projects next need to share authentication (e.g., anyone touches DozerDB with a rotated password), the ADR that does the rotation must update both `.env` files.

### D4 — Migration path if Option B ever becomes necessary

The plan's Option B trigger is "resource contention or query-pattern conflict under real load". If either occurs post-Stage-5, the escape hatch is:

1. Kosmos brings up a second DozerDB via a new compose file with a different container name (e.g., `kosmos-dozerdb-memory`) and port bindings (e.g., `7475:7474` + `7688:7687`).
2. Kosmos memory plugins' `MEMORY_BOLT_URI` env var repoints to the new instance.
3. Forge-OH keeps the current `kosmos-dozerdb` container and `bolt://127.0.0.1:7687` unchanged.

The `forgeoh` database name and Forge-OH BFF settings do not change. This ADR therefore does not need to be superseded to move to Option B — only amended with a "STATUS AMENDMENT" banner documenting the split.

## Consequences

### Positive

- **Zero code changes for Stage 4.5.** The consolidation is already implemented; this ADR ratifies it.
- **Single operational footprint on Colossus.** One graph database to back up, patch, restart. The plan's stated Colossus-first mandate is honored.
- **Database-name isolation is well-supported.** Neo4j (and DozerDB by extension) has first-class multi-database support; RepoGraph's `forgeoh_*` constraint/index prefixes prevent even accidental namespace collision at the schema level.
- **Kosmos ownership is codified.** Future Forge-OH sessions cannot silently drift into forking a duplicate DozerDB compose — they must read this ADR first.

### Negative

- **Cross-repo coupling on the DozerDB config.** Forge-OH's operational correctness depends on Kosmos's `ops/compose/memory.yml`. If Kosmos removes the `apoc` plugin, bumps the image tag, or changes the port bindings, Forge-OH breaks silently until re-verified. Mitigated by: `PORTING_LEDGER.md` records the exact Kosmos commit SHA and Forge-OH's `docs/adr/019-dozerdb-consolidation.md` (this file) is the entry point that lists the exact expected image and ports.
- **Shared blast radius.** A DozerDB restart affects both Forge-OH RepoGraph and any Kosmos plugin using it simultaneously. For single-user Colossus this is acceptable.
- **Password drift risk.** D3 explicitly permits Forge-OH and Kosmos to hold different passwords transiently. A rotation on one side without the other must be caught by BFF health checks; no automated reconciliation exists.

### Neutral / deferred

- **APOC plugin availability.** Kosmos's compose enables APOC. Forge-OH does not currently depend on APOC, but has access to it. If Forge-OH adopts an APOC procedure later, this ADR is the pointer to the fact that APOC is available; no separate ADR is needed unless the dependency becomes load-bearing.

## Cross-references touched by this ADR

- **New file:** `docs/adr/019-dozerdb-consolidation.md` (this ADR).
- **`AGENTS.md`:** append a "Graph storage" section pointing at Kosmos's `ops/compose/memory.yml` as the canonical DozerDB spec and this ADR as the authoritative decision.
- **`PORTING_LEDGER.md`:** add a Kosmos-donor reference entry — dependency-only (Forge-OH does not vendor Kosmos code), source URL `github.com/rmholston420/kosmos`, path `ops/compose/memory.yml`, pinned commit SHA (recorded at ADR-write time), SPDX license from Kosmos repo LICENSE file.
- **`docs/reconciliation-plan-stage-4.md § 4.5`:** amend to note the decision is Option A and the discovery removed the need for code changes. Cross-reference this ADR.
- **`docs/adr/README.md`:** append the ADR-019 index entry.
- **`BUILD_LOG.md`:** append the Stage 4.5 decision entry per the plan's template.
