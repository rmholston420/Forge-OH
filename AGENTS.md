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

---

## Working with Slices

Before implementing any slice:
- Read the slice checklist in `docs/slices/<slice-id>/CHECKLIST.md`.
- Read the route contract in `docs/slices/<slice-id>/README.md`.
- Read `.openhands/context/conventions.md` for coding standards.
- Read `.openhands/context/architecture.md` for layer boundaries.

Every slice deliverable must satisfy the **Definition of Done** in
`docs/DEFINITION_OF_DONE.md` before it can be merged.

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
