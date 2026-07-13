# ADR 002: The Browser Never Calls OpenHands Directly

**Status:** Accepted  
**Date:** 2026-07

## Context

OpenHands exposes a powerful agentic execution environment. If the browser could
call it directly, we would have no control plane for loop detection, context
injection, model routing, or access control.

## Decision

All OpenHands interactions are mediated by the BFF:

- `bff/routers/runs.py` starts/stops runs.
- `bff/services/loop_guard.py` detects and breaks action loops before they
  exhaust the context window.
- `bff/services/context_loader.py` injects ADRs and conventions from
  `.openhands/context/` into every planning step.
- `bff/services/episodic_memory.py` persists cross-session facts.
- `bff/services/conflict_checker.py` detects git merge conflicts before runs.

The browser communicates with the BFF via REST (via Next.js API route handlers
for proxying) and Socket.IO for streaming events.

## Consequences

- All security, rate-limiting, and observability logic lives in the BFF.
- OpenHands sandbox is not exposed on any public port.
