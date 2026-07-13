# ADR 004: src/lib/rbac/ — Rigpa-LMS Role Integration

**Date**: 2026-07-13  
**Status**: Accepted (forward-looking)  
**Deciders**: rmholston420

---

## Context

`src/lib/rbac/` exists in the codebase but is not defined in the Phase 0–4
repository structure in the build spec. It was added in anticipation of
Phase 5C (Rigpa-LMS Plugin Integration Layer).

## Decision

1. **`src/lib/rbac/` is accepted** as a forward-looking addition.

2. **It must be gated behind `FEATURE_RIGPA_LMS_ENABLED`.**  
   No component, hook, or route in Phases 0–4 may import from `src/lib/rbac/`
   without checking `isFeatureEnabled('RIGPA_LMS')` first.

3. **It must not affect Phase 0–4 functionality.**  
   If the RIGPA_LMS feature flag is off (the default), no RBAC logic
   should execute at runtime.

4. **Phase 5C (Slice 5C) owns this directory.**  
   All substantive RBAC logic should be held until Slice 5C is scoped
   and implemented. This directory is a placeholder scaffold only until then.

## Relevant spec section

> **Slice 5C — Rigpa-LMS Plugin Integration Layer**  
> LMS user ID → Forge session and policy profile.  
> LMS role (instructor/student) → tool permission policy.  
> Course enrollment → workspace access control.

## Consequences

- `src/lib/rbac/` is permitted to exist as a scaffold.
- It must remain inert (feature-flagged off) until Slice 5C is implemented.
- All agents building Phases 0–4 must treat `src/lib/rbac/` as out-of-scope.
