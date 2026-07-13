# ADR 003: State Management Architecture

**Date:** 2026-07-10  
**Status:** Accepted

## Context

Forge-OH requires state management across three distinct domains:
1. **Server state** — data fetched from the BFF (runs, workspaces, secrets, agent presets)
2. **UI state** — local ephemeral state (selected tab, inspector open, command palette)
3. **Stream state** — real-time Socket.IO event accumulation per run

Using a single global store for all three conflates concerns with very different lifecycles and invalidation strategies.

## Decision

Adopt a layered state architecture:

| Layer | Tool | Scope | Examples |
|---|---|---|---|
| Server state | TanStack Query v5 | Global cache | Runs list, run detail, workspaces |
| App UI state | Zustand (`app-store.ts`) | Global, persistent | Active route, sidebar, command palette |
| Run detail UI | Zustand (`ui-store.ts`) | Per-run, reset on navigate | Selected tab, inspector, stream cursor |
| Stream state | Zustand (`streaming-store.ts`) | Per-run, ephemeral | Accumulated `oh-event` payloads |

## Consequences

- TanStack Query handles cache invalidation, background refetching, and loading/error states for all BFF data — no manual fetch coordination.
- `ui-store.ts::resetRunDetailUI()` **must** be called when navigating between runs to reset `latestStreamEventId` to 0; failure to call it causes the Socket.IO stream to reconnect from a stale cursor and skip events.
- Zustand stores are typed with explicit `State` + `Actions` interface separation; selectors are defined as pure functions at the bottom of each store file.
- No Redux. No Context API for frequently-updating state.
