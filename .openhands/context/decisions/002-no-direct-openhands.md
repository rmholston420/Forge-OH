# ADR-002: Frontend Never Talks Directly to OpenHands

**Status**: Accepted  
**Date**: 2026-07-12

## Decision

All frontend traffic routes through the BFF. The frontend has no direct connection to OpenHands.

## Rationale

- BFF is the policy injection point: course context, loop-guard, episodic memory
- BFF normalizes all upstream OpenHands payload shapes
- BFF redacts secrets before any data reaches the browser
- BFF enforces delegation contract templates on every agent dispatch

## Consequence

All API routes live under `/api/` in the Next.js app, which proxies to the FastAPI BFF.
