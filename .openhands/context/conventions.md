# Forge-OH Coding Conventions

## TypeScript

- strict: true is on by default (TS 6.0)
- Run `tsc --noEmit` before every CI gate
- All domain objects have Zod schemas in `src/lib/schemas/`
- Use exact names from domain model — NEVER rename domain objects
- Feature flags: `NEXT_PUBLIC_FEATURE_[SLICE_NAME]_ENABLED`

## CSS

- Use ONLY token names from `src/styles/tokens.css`
- NEVER invent new token names
- CSS Modules for all component styles
- Dimensions from tokens, NEVER hardcoded

## Python (BFF)

- Python 3.13, FastAPI 0.136, Pydantic 2.12
- All routes return `{"data": ..., "stub": bool}` shape in Phase 0
- Secret values NEVER in API responses — maskedValue only

## Testing

- Vitest for unit/integration
- Playwright for E2E
- MSW fixtures must mirror live OpenHands payload shapes
- Every slice needs unit + integration + E2E coverage
