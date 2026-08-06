# Forge-OH Architectural Decision Records

Index of ADRs under `docs/adr/`. Numbering is sequential; gaps (e.g. ADR-010) are historical skips that predate this index.

| ID | Title | Status | Supersedes | Superseded by |
|----|-------|--------|------------|---------------|
| [003](./003-state-management.md) | State management | Accepted | — | — |
| [004](./004-bff-middleware.md) | BFF middleware | Accepted | — | — |
| [005](./005-rbac-lib.md) | RBAC lib | Accepted | — | — |
| [006](./006-repograph.md) | Repograph | Accepted | — | — |
| [007](./007-verify-loop.md) | Verify loop | Accepted | — | — |
| [008](./008-trajectory-memory.md) | Trajectory memory | Accepted | — | — |
| [009](./009-local-llm-selection.md) | Local LLM selection (coder + planner roles) | Accepted (routing-layer superseded) | ADR-001 (Ollama-first) | [ADR-012](./012-dual-mode-model-routing.md) (routing contract only; §3a topology + §3b budgets + §5 notes retained) |
| [011](./011-selfeval-harness.md) | Self-eval harness | Accepted | — | — |
| [012](./012-dual-mode-model-routing.md) | Dual-mode model routing — role-first with preset model override | Accepted | ADR-009 §1, §2, §3, §3a (routing-layer contract) | — |
| [013](./013-qwen36-27b-canonical-coder-planner.md) | Canonical coder + planner (F.1b ratified · F.3 full-500 validated) | Amended · Planner ratified 2026-08-05 03:52 · Coder ratified 2026-08-05 04:55 (F.1b) · F.3 full-500 pass@1 = 26.6% / 28.6% attempted-only (2026-08-05 19:20) | ADR-009 §1 + §2 | — |
| [015](./015-swe-bench-sandbox.md) | SWE-bench sandbox | Accepted | — | — |
| [016](./016-colossus-github-mirror-parity.md) | Colossus ↔ GitHub mirror parity | Ratified | — | — |
| [017](./017-bench-nvml-mandatory.md) | NVML GPU sampling mandatory on every bench harness | Ratified | — | — |
| [018](./018-serena-lspclient-integration.md) | Serena LSPClient integration via MCP passthrough (Stage 4.4) | Accepted | — | — |
| [019](./019-dozerdb-consolidation.md) | DozerDB consolidation: Kosmos-canonical shared instance (Stage 4.5) | Accepted | — | — |
| [020](./020-qwen3-embedding-default.md) | Qwen3-Embedding as Forge-OH's default EmbeddingsPort model (Stage 5.2) | Accepted | — (departs from Kosmos upstream `nomic-embed-text` default) | — |
| [021](./021-memory-adapter-graph-shape.md) | Memory adapter graph shape: CIDOC-native triples + MemoryEvent node + fulltext temporal index (Stage 5.3b) | Ratified | — (Kosmos ADR-027 inherited; D5 diverges to `NoOpAmgPolicy`, TemporalIndex replaces deleted `GraphitiTemporalIndex` from Kosmos ADR-075 D1) | — |
| [022](./022-stage-5-4-zero-trust-satisfied-by-port-layer.md) | Stage 5.4 zero-trust write enforcement satisfied by ported port-layer validators | Ratified | Plan §5.4.2 proposed `MemoryWriteEvent` pydantic model (superseded — port-layer validators are stricter) | — |
| [023](./023-ace-curation-cycle.md) | ACE-style memory curation cycle: triple-shaped, deterministic string-overlap first pass, library-only until a caller exists (Stage 5.5) | Ratified | Plan §5.5.1 + §5.5.2 free-string sketches (superseded — ADR-021 D1 pins `:MemoryEvent` as triple-shaped) | — |

## Authoring workflow

New or amended ADRs follow the `kosmos-adr-authoring` skill. Filename pattern: `NNN-kebab-case-title.md`. Amendments are prepended as a `> **STATUS AMENDMENT (YYYY-MM-DD):** ...` block above the original front matter; the original decision text is never deleted.

## Skipped numbers

- **ADR-001, ADR-002** live under `.openhands/decisions/` (predate `docs/adr/`).
- **ADR-010** unassigned (historical gap).

| 015 | [SWE-bench Verified end-to-end sandbox](015-swe-bench-sandbox.md) | Proposed | Adds Stage-1H: per-run Docker sandbox for full-Forge-OH Verified acceptance |
| 016 | [Colossus<->GitHub mirror parity](016-colossus-github-mirror-parity.md) | Ratified | Cross-cutting: every file tracked or explicitly ignored; Perplexity Computer commits directly to GitHub (user pulls); enforced by AGENTS.md #9+#10 + forge-doctor §10 + pre-commit hook |
| 017 | [NVML GPU sampling mandatory on every bench](017-bench-nvml-mandatory.md) | Ratified | Cross-cutting: every bench harness under `bench/` imports `GpuSampler` from `bench._common.nvml_sampler` and persists per-task `gpu_inference` (+ optional `gpu_harness`) plus a run-level `gpu` aggregate |
