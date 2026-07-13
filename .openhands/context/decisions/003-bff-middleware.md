# ADR 003: BFF Middleware Directory

**Date**: 2026-07-13  
**Status**: Accepted  
**Deciders**: rmholston420

---

## Context

The `bff/` directory contains a `middleware/` subdirectory that is not
explicitly defined in the Forge-OH-Build-Plan-Definitive.md repository
structure. This ADR documents its purpose and constraints.

## Decision

The `bff/middleware/` directory is an accepted addition to the spec
structure, subject to the following hard constraints:

1. **No middleware may bypass the BFF gatekeeper contract.**  
   The architecture rule is absolute: _the frontend never talks directly
   to OpenHands_. No middleware may accept or forward raw OpenHands
   payloads without going through `openhands_client.py`.

2. **Auth middleware must call `openhands_client.py`**, not OpenHands REST
   endpoints directly.

3. **No secret values may pass through middleware to the frontend.**  
   The `redact_secrets()` function in `openhands_client.py` is the
   authoritative redaction layer. Middleware must not short-circuit it.

4. **Middleware must be documented here** as each module is added.

## Current middleware modules

| Module | Purpose |
|--------|---------|
| _(to be filled as modules are added)_ | |

## Consequences

- Middleware is permitted but strictly gated by these constraints.
- Any middleware that talks to OpenHands directly is a build-system error
  and must be flagged in code review.
