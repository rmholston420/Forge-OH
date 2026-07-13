# ADR 003 — Rigpa-LMS Plugin Architecture

**Status:** Accepted  
**Date:** 2026-07-13  
**Slice:** 5C — Rigpa-LMS Plugin Integration Layer

## Context

Forge-OH will eventually be embedded as a plugin panel inside the Rigpa-LMS learning management system. Instructors and students will launch AI-assisted workflows (exercise generation, code review, assessment, content authoring) from within LMS course pages. Each LMS session carries rich pedagogical context that must be injected into every agent task to make the AI output educationally relevant and auditable.

## Decision

1. **Context injection via `RigpaAgentLaunchContext`** — the LMS plugin shell sends a typed JSON envelope to the Forge BFF on session start. The BFF transforms this into an OpenHands task context and policy envelope. The frontend never constructs this envelope directly.

2. **Ribbon, not modal** — the LMS context is surfaced as a persistent ribbon above the main content (not a modal or sidebar) so course context is always visible during agent supervision.

3. **Feature flag** — the entire LMS integration layer is gated behind `FEATURE_RIGPA_LMS_ENABLED` (BFF) and `NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED` (frontend). Forge-OH operates as a standalone tool when these are `false`.

4. **postMessage + env var dual injection** — the frontend listens for `RIGPA_LMS_LAUNCH_CONTEXT` postMessage from the LMS iframe host AND checks `NEXT_PUBLIC_RIGPA_LMS_CONTEXT` for server-side embed scenarios. Zod validates both paths.

5. **Artifact-to-LMS packaging** — completed run artifacts are packaged back to the LMS via `POST /api/lms/package`. The target LMS object type is derived from the session `taskType`. The LMS Exchange API call is stubbed in Phase 5C and wired in Phase 6.

6. **Iframe safety** — the ribbon uses `position: relative` (not `fixed` or `sticky`) so it works correctly inside LMS iframe panels that control their own scroll context.

## Consequences

- Every agent session launched from the LMS is reproducible and auditable within LMS context.
- Disabling `FEATURE_RIGPA_LMS_ENABLED` leaves zero LMS surface area in the UI.
- Phase 6 wires the LMS Exchange API, SSO session handoff, and per-course workspace access control.
- The `src/lib/rbac/` module should be gated behind this same flag until Phase 6 role-based permissions are implemented.
