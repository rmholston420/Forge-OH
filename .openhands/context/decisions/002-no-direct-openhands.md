# ADR 002 — Frontend Never Talks Directly to OpenHands

**Status**: Accepted  
**Date**: July 2026

## Context

The OpenHands SDK exposes a rich REST and WebSocket API. It is tempting to call it directly from the frontend for simplicity, especially during early development.

## Decision

The frontend is **permanently** prohibited from importing, calling, or connecting directly to any OpenHands endpoint. All traffic flows through the Forge BFF.

## Rationale

1. **Policy injection**: The BFF is the only place that injects loop-guard enforcement, course context, episodic memory, and delegation contracts. Direct calls bypass all safety policies.
2. **Secret isolation**: OpenHands may have access to workspace secrets. The BFF enforces that raw values never reach the frontend.
3. **Rigpa-LMS integration**: Course context enrichment happens in the BFF. Direct calls produce context-blind agent behavior.
4. **Audit trail**: All agent instructions must pass through the BFF audit log.

## Enforcement

- ESLint rule banning direct imports of `@all-hands-ai/openhands` in `src/`
- CI check: `grep -r 'openhands' src/ --include='*.ts' --include='*.tsx'` must return zero results
- All OpenHands calls are in `bff/openhands_client.py` only
