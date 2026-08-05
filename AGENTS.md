# Forge-OH — AI Agent Execution Contract

This file is the **mandatory first read** for any AI agent (Perplexity Computer,
Claude Code, OpenHands, Copilot) working on this repository.

---

## Non-Negotiable Rules

1. **Never talk directly to OpenHands.** All traffic routes through the BFF.
   The `NEXT_PUBLIC_OPENHANDS_URL` env var must never appear in frontend code.

2. **Never invent token names.** Every color, spacing, typography, radius, and
   motion value must use a token defined in `src/styles/tokens.css`.

3. **Never hardcode model names in the frontend.** Model routing is the BFF's
   responsibility (`bff/services/model_router.py`).

4. **Every slice must be feature-flagged** with `FEATURE_<SLICE>_ENABLED` (BFF)
   and `NEXT_PUBLIC_FEATURE_<SLICE>_ENABLED` (frontend).

5. **TypeScript strict mode is always on.** Run `tsc --noEmit` before any commit.
   Zero errors is the gate.

6. **Secret values never reach the browser.** The BFF redacts all raw values.
   `maskedValue` only. Raw secrets are a Critical risk.

7. **Control plane ≠ target plane.** Agents may modify the checked-out branch
   (target plane) but must never self-modify the running Forge-OH instance
   (control plane) without elevated approval.

8. **Every domain object uses the canonical names** from `DOMAIN_MODEL.md`.
   Never rename: Run, AgentPreset, Workspace, ToolEvent, Artifact, Integration,
   TraceSpan, SecretRef, PlanNode, CommandExecution, BrowserSession.

9. **Colossus <-> GitHub mirror parity is mandatory** (ADR-016). Every file on
   Colossus at `~/dev/forge-oh/` is either tracked in git or explicitly ignored
   via `.gitignore` with a comment justifying why. No untracked-but-not-ignored
   files. **Perplexity Computer commits directly to GitHub via `bash` with
   `api_credentials=["github"]`; the user pulls with `git pull`.** No paste-
   block commit workflows. Every commit pushes the same turn. Run
   `bash scripts/forge-doctor.sh` at session start and end to detect drift. The
   pre-commit hook at `scripts/pre_commit_drift_check.sh` (installed via
   `.pre-commit-config.yaml`) blocks accidental drift-introducing commits
   (overridable with `git commit --no-verify` only for legitimate WIP).

10. **Selfeval artifact retention policy** (ADR-016). Commit selfeval outputs
    only when they carry signal:
    - `docs/selfeval/*.md` analysis/scope docs -> always commit.
    - `docs/selfeval/*.json` result summaries -> commit only if at least one
      task produced real signal (not all-environmental-error like vLLM :8501
      down).
    - `docs/proposals/*.md` proposer LLM outputs -> commit only if the proposer
      LLM was healthy for that run (not `Connection refused` failures).
    Environmental failures belong in `DEBUG_LOG.md`, not `docs/proposals/`.

---

## Canonical Planning Documents

`docs/reconciliation-plan-v1.md` is the **canonical, authoritative execution
plan** for all Forge-OH work. It supersedes `Forge-OH-Action-Plan-v4.md`
entirely. Historical BUILD_LOG.md entries reference v4 by name — those
remain as append-only history, but no new work stages from v4.

Stage-specific companion docs live at `docs/reconciliation-plan-stage-*.md`
(e.g. `docs/reconciliation-plan-stage-1H.md`).

Before starting any stage or slice: read `SESSION_HANDOFF.md` first, then
the relevant stage in `docs/reconciliation-plan-v1.md`.

## Working with Slices

Slice mechanics (checklist + route contract + Definition of Done) still apply
when a stage of the reconciliation plan is broken into slices:

- Read the slice checklist in `docs/slices/<slice-id>/CHECKLIST.md` if it exists.
- Read the route contract in `docs/slices/<slice-id>/README.md` if it exists.
- Read `.openhands/context/conventions.md` for coding standards.
- Read `.openhands/context/architecture.md` for layer boundaries.

Every deliverable must satisfy the **Definition of Done** in
`docs/DEFINITION_OF_DONE.md` before it can be merged. When the reconciliation
plan's per-stage stop condition is stricter than DoD, the stricter condition wins.

---

## Commit Message Format

```
feat(<slice>): <description>
fix(<slice>): <description>
chore: <description>
docs: <description>
test(<slice>): <description>
```

Examples:
- `feat(1A): runs home page with new run composer`
- `fix(2A): diff viewer fails on binary files`
- `test(3C): secrets SecretRow masking unit tests`

---

## Directory Quick-Reference

| Path | Purpose |
|------|---------|
| `src/features/<slice>/` | Feature logic: api, hooks, store, schemas, mappers, fixtures |
| `src/components/domain/` | Shared domain components (RunCard, EventCard, …) |
| `src/components/core/` | Primitives (Button, Input, Badge, …) |
| `src/lib/schemas/` | Zod schemas for all domain objects |
| `src/lib/api/` | BFF client layer (client, endpoints, errors, response) |
| `src/lib/state/` | Zustand app-store and ui-store |
| `src/tests/mocks/` | MSW handlers and server setup |
| `src/tests/fixtures/` | Typed fixture data mirroring live payload shapes |
| `bff/routers/` | FastAPI route handlers |
| `bff/services/` | BFF services (loop-guard, context-loader, …) |
| `.openhands/context/` | ADRs, architecture, conventions, personas |
| `docs/slices/` | Per-slice README contracts and checklists |
