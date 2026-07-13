# ADR 002: Frontend Never Talks Directly to OpenHands

**Status**: Accepted  
**Date**: 2026-07-01

## Context

OpenHands exposes a REST + WebSocket API. The simplest integration would have the frontend call OpenHands directly. However, this creates several problems:

1. No policy injection point for course context, loop-guard, or episodic memory.
2. Raw OpenHands events are not shaped for UI consumption.
3. Secrets and model routing decisions would be exposed to the browser.
4. The LMS plugin layer (Phase 5C) cannot intercept or augment calls.

## Decision

All traffic flows through the Forge BFF. The frontend never holds an OpenHands URL or API key. The BFF:

1. Authenticates with OpenHands using server-side credentials.
2. Injects course context and ADRs before dispatching agent tasks.
3. Enforces loop-guard and escalation policies.
4. Normalizes OpenHands events into the Forge domain model before forwarding to the frontend.
5. Proxies WebSocket streams through Socket.IO, translating OpenHands events to `oh_event` messages.

## API Contract Boundary

```
Frontend  →  Next.js API routes (src/app/api/)  →  Forge BFF  →  OpenHands
```

The Next.js API routes are thin proxies — they add auth headers and forward. Business logic lives only in the BFF.

## Consequences

- `NEXT_PUBLIC_*` env vars must never contain OpenHands credentials.
- `openhands_client.py` is the only file in the codebase that holds the OpenHands base URL.
- BFF routers validate all input with Pydantic before forwarding to OpenHands.
- This architecture enables the Rigpa-LMS plugin (Phase 5C) to inject course context at the BFF layer without frontend changes.
