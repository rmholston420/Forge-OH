# ADR 004: BFF Middleware Stack

**Date:** 2026-07-10  
**Status:** Accepted

## Context

The BFF needs request authentication, role-based access control, and observability without scattering those concerns across individual route handlers.

## Decision

Apply a layered FastAPI middleware stack in `bff/main.py`:

1. **CORS** — `CORSMiddleware` with an allowlist from `settings.allowed_origins`
2. **Auth** — `AuthMiddleware` reads the `Authorization: Bearer <token>` header, validates the token against `auth_state.py`, attaches `request.state.user_id` and `request.state.role`
3. **RBAC** — `require_role()` FastAPI dependency used at the router level for write/delete endpoints
4. **Observability** — `OpenTelemetryInstrumentationFastAPI` wraps each request/response in an OTLP span

## Consequences

- Route handlers are clean — they read `request.state.user_id` without re-validating.
- Token TTL (8 hours) is enforced in `AuthMiddleware`; expired tokens return 401.
- RBAC guards on MCP write/delete and plugin write/delete/install prevent privilege escalation.
