# Definition of Done — Every Slice

A slice is **done** only when ALL of the following are true:

## Implementation
- [ ] UI implementation complete for all states listed in slice spec
- [ ] All loading, empty, error, and degraded states handled explicitly
- [ ] Responsive verified at 1280px, 1440px, 1920px
- [ ] Feature flag gating `NEXT_PUBLIC_FEATURE_<SLICE>_ENABLED` in place

## Contracts
- [ ] TypeScript interfaces defined for all data shapes
- [ ] Zod schemas in `src/lib/schemas/` for every domain object touched
- [ ] Mock fixture in `src/tests/fixtures/` mirrors live payload shape exactly
- [ ] BFF route contract documented in `docs/slices/<slice-id>/README.md`

## Quality
- [ ] Zero TypeScript errors (`tsc --noEmit`)
- [ ] Zero ESLint errors
- [ ] Unit tests for critical logic (mappers, status utils, schema validation)
- [ ] Integration test for primary happy path
- [ ] E2E smoke test: route loads, critical elements visible
- [ ] Accessibility: keyboard navigation, ARIA labels, contrast pass
- [ ] Basic instrumentation hook in place

## Design
- [ ] Only existing design tokens used — no new token names invented
- [ ] Only existing component names from domain model — no new visual language
- [ ] All interactive states: default, hover, focus, disabled, loading, error
