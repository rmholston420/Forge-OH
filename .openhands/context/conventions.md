# Forge-OH Code Conventions

## Naming

- **Domain objects use canonical names — never rename them.** `Run`, `AgentPreset`, `Workspace`, `ToolEvent`, `Artifact`, `Integration`, `TraceSpan`, `SecretRef`, `PlanNode`, `CommandExecution`, `BrowserSession`.
- Feature folders mirror the domain: `src/features/runs/`, `src/features/run-detail/`, `src/features/workspaces/`, etc.
- API routes follow REST conventions: `GET /api/runs`, `POST /api/runs`, `GET /api/runs/:id/events`.
- CSS tokens use `--color-`, `--space-`, `--font-`, `--motion-`, `--layout-` prefixes — never invent new token names.

## TypeScript

- `strict: true` is enabled. Run `tsc --noEmit` before every commit.
- All API response shapes are validated with Zod schemas in `src/lib/schemas/`.
- Interfaces for domain objects live in `src/lib/schemas/` — never duplicate them inline.
- No `any` types. Use `unknown` + Zod parse for external data.

## Frontend Component Structure

Every core component has three files:
```
ComponentName.tsx
ComponentName.module.css
ComponentName.stories.tsx
```

Domain components in `src/components/domain/` follow the same pattern.

## State

- **Never fetch data in a component.** Use TanStack Query hooks from `src/features/<feature>/hooks/`.
- **Never put server data in Zustand.** Zustand owns UI state only.
- **Never access the BFF URL directly from a component.** All fetches go through `src/lib/api/client.ts`.

## Styling

- CSS Modules only — no inline styles, no Tailwind, no styled-components.
- All color, spacing, and motion values must reference a CSS custom property from `tokens.css`.
- Never hardcode hex values or pixel values in component CSS.

## BFF (Python)

- All routers are in `bff/routers/`. Never put business logic in router handlers.
- Business logic lives in `bff/services/`.
- The ASGI entry point is `bff.main:app_with_sio` — never `bff.main:app`.
- All outbound calls to OpenHands go through `bff/openhands_client.py`.

## Testing

- Unit tests: Vitest, co-located as `*.test.ts` or in `src/tests/unit/`.
- E2E tests: Playwright, in `src/tests/e2e/`.
- All base layouts must render from MSW mocks — zero live service dependency in tests.

## Git

- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- No direct pushes to `main` for feature work — use feature branches and PRs.
- Exception: infrastructure/scaffolding changes may be committed directly to `main` during Phase 0.
