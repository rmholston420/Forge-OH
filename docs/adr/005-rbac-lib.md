# ADR 005: RBAC Library Selection

**Date:** 2026-07-10  
**Status:** Accepted

## Context

Forge-OH needs role-based access control for the BFF. Options considered: Casbin (powerful, complex), OPA (network-policy sidecar, overkill for a single-service BFF), or a hand-rolled dependency.

## Decision

Use a hand-rolled `require_role()` FastAPI dependency (`bff/middleware/rbac.py`) backed by a simple role hierarchy dict:

```
viewer < operator < admin
```

The dependency accepts `minimum_role: str` and raises `HTTP 403` if `request.state.role` does not meet the minimum. Role is stamped onto `request.state` by `AuthMiddleware` (see ADR 004).

## Consequences

- No external RBAC library dependency — reduces attack surface and keeps the BFF self-contained.
- Extending roles requires updating the hierarchy dict and re-deploying the BFF.
- If role complexity grows beyond 3 levels or cross-resource policies are needed, revisit Casbin.
