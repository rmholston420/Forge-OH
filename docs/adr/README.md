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
| [013](./013-qwen36-27b-canonical-coder-planner.md) | Canonical coder + planner (F.1b ratified) | Amended · Planner ratified 2026-08-05 03:52 · Coder ratified 2026-08-05 04:55 (F.1b) | ADR-009 §1 + §2 | — |

## Authoring workflow

New or amended ADRs follow the `kosmos-adr-authoring` skill. Filename pattern: `NNN-kebab-case-title.md`. Amendments are prepended as a `> **STATUS AMENDMENT (YYYY-MM-DD):** ...` block above the original front matter; the original decision text is never deleted.

## Skipped numbers

- **ADR-001, ADR-002** live under `.openhands/decisions/` (predate `docs/adr/`).
- **ADR-010** unassigned (historical gap).

| 015 | [SWE-bench Verified end-to-end sandbox](015-swe-bench-sandbox.md) | Proposed | Adds Stage-1H: per-run Docker sandbox for full-Forge-OH Verified acceptance |
| 016 | [Colossus<->GitHub mirror parity](016-colossus-github-mirror-parity.md) | Ratified | Cross-cutting: every file tracked or explicitly ignored; Perplexity Computer commits directly to GitHub (user pulls); enforced by AGENTS.md #9+#10 + forge-doctor §10 + pre-commit hook |
