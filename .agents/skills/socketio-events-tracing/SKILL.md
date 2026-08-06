---
name: socketio-events-tracing
description: How to instrument, trace, and debug Socket.IO events flowing through Forge-OH's BFF and frontend. Use whenever adding a new event type, emitting events from the BFF, subscribing in a React component, debugging why an event isn't received, or reading the trace/event log. Enforces the app_with_sio wrapper rule, event namespace conventions, and structured payload discipline.
license: MIT
triggers:
  - socket.io
  - "socketio"
  - "app_with_sio"
  - sio.emit
  - "sio_server"
  - useSocket
  - useSocketEvent
  - "src/lib/streaming"
  - event_relay
  - event_normalize
  - trace event
  - "eventBus"
  - SSE
  - websocket
---

# Socket.IO Events & Tracing in Forge-OH

## Architecture

- **Server**: Socket.IO ASGI server, mounted alongside FastAPI via `app_with_sio` in `bff/main.py`
- **Emit side**: `bff/services/event_relay.py` bridges normalized agent-server events → Socket.IO clients
- **Event shape**: normalized via `bff/services/event_normalize.py` (see `_KIND_TO_TYPE` dict)
- **Client**: React hooks in `src/lib/streaming/` subscribe to specific event types

## Non-Negotiable Rules

1. **BFF must be started with `bff.main:app_with_sio`, NEVER `bff.main:app`.** The plain `app` has no Socket.IO wrapper → all real-time events silently drop.
2. **Never invent a new event type inline.** Add it to `_KIND_TO_TYPE` in `event_normalize.py` and the FE schema `src/lib/schemas/event.ts`.
3. **Payloads pass through `raw` unchanged.** Add fields to the top-level projection, but keep the original in `raw` so the event-detail drawer keeps working.
4. **One event = one intent.** Don't cram multiple state transitions into one event.
5. **Event names on the wire match `_KIND_TO_TYPE` values, not the SDK class names.** SDK emits `Condensation`, wire emits `condensation`.

## Verified BFF Startup

```bash
cd ~/dev/forge-oh
nohup .oh-venv/bin/uvicorn bff.main:app_with_sio \
  --host 127.0.0.1 --port 8081 \
  >~/.forge-oh/bff.log 2>&1 &
```

If Socket.IO events don't arrive at the browser:
- First check: was BFF started with `app_with_sio`? Grep the log or `ps aux | grep uvicorn`.
- If started with `app` only, Socket.IO is unmounted → restart with `app_with_sio`.

## Event Normalization

Canonical projection from `event_normalize.py`:

```python
_KIND_TO_TYPE: dict[str, str] = {
    "MessageEvent": "message",
    "ActionEvent": "action",
    "ObservationEvent": "observation",
    "AgentErrorEvent": "error",
    "ConversationErrorEvent": "error",
    "ConversationStateUpdateEvent": "status",
    "Condensation": "condensation",
    "CondensationRequest": "condensation_request",
    "CondensationSummaryEvent": "condensation_summary",
    "LLMCompletionLogEvent": "status",
    "PauseEvent": "run_paused",
    "SystemPromptEvent": "status",
    "TokenEvent": "status",
    "MemoryConsultationEvent": "memory_consultation",
    "WebSearchEvent": "web_search",
}
```

**Rules:**
- New SDK event class → add mapping in `_KIND_TO_TYPE`
- New event type on the wire → add to `src/lib/schemas/event.ts` Zod schema too
- Multiple SDK classes can map to one wire type (e.g., both `AgentErrorEvent` and `ConversationErrorEvent` → `error`)
- Never drop unrecognized fields from the raw event — pass them through in `raw`

Standard event envelope:

```typescript
{
  id: string,        // unique per event
  type: string,      // from _KIND_TO_TYPE, lowercased
  timestamp: string, // ISO-8601
  source: string,    // "agent" | "user" | "system" | ...
  summary: string,   // pre-rendered short text for cards
  raw: object        // untouched original event
}
```

## Emit Side (BFF)

```python
# bff/services/event_relay.py pattern
from bff.main import sio  # the Socket.IO server instance

async def emit_run_event(run_id: str, event: dict):
    await sio.emit(
        "run_event",             # channel name — see channel conventions below
        event,
        room=f"run:{run_id}",    # only clients subscribed to this run
    )
```

### Channel conventions

- `run_event` — normalized run events (message, action, observation, error, status, …)
- `run_status` — high-level run lifecycle (queued, running, completed, cancelled)
- `gpu_health` — GPU strip updates (temperature_c, utilization_pct, vram_pct, power_w)
- `notification` — user-facing notifications

New channel? Document it in `docs/socketio-channels.md` and add a matching FE hook.

### Rooms

- `run:<run_id>` — everyone watching a specific run
- `user:<user_id>` — user-scoped (currently just single-user, but future-proof)
- `session:<session_id>` — for cross-tab sync

Emit to the narrowest room possible. Never `sio.emit(..., room=None)` — that broadcasts to everyone.

## Subscribe Side (Frontend)

```typescript
// src/lib/streaming/useSocket.ts (existing helper)
import { useEffect } from "react";
import { getSocket } from "./socketio";
import { EventSchema } from "@/lib/schemas/event";

export function useRunEvents(runId: string, onEvent: (event: Event) => void) {
  useEffect(() => {
    const socket = getSocket();
    socket.emit("join", { room: `run:${runId}` });

    const handler = (raw: unknown) => {
      const parsed = EventSchema.safeParse(raw);
      if (!parsed.success) {
        console.error("Invalid event", parsed.error);
        return;
      }
      onEvent(parsed.data);
    };

    socket.on("run_event", handler);
    return () => {
      socket.off("run_event", handler);
      socket.emit("leave", { room: `run:${runId}` });
    };
  }, [runId, onEvent]);
}
```

**Rules:**
- One subscription per component; always clean up in the effect return
- Zod-parse every incoming event; log parse failures — don't silently drop
- Never subscribe outside a component / hook (memory leaks)
- Batch updates in the reducer if the event rate is high (>10/sec)

## Debugging: Events Not Arriving

1. **Check BFF startup**: `ps aux | grep uvicorn` — confirm `app_with_sio`, not `app`
2. **Check BFF log**: `tail -f ~/.forge-oh/bff.log` — look for emit lines
3. **Check browser Network tab**: filter to WS, click the Socket.IO connection, view Messages
4. **Check the room**: is the client actually in the room the emit targeted?
5. **Check the event name**: `sio.emit("run_event", ...)` on server, `socket.on("run_event", ...)` on client — names must match exactly
6. **Check the schema**: if Zod rejects the payload, the event drops silently (unless you logged it) → log Zod failures
7. **Search DEBUG_LOG.md** for prior similar symptoms (mandatory per project instructions)

## Debugging: Event Rate Too High

Symptoms: browser tab slow, React re-renders spike, memory grows.

Fixes (in order of preference):
1. **Server-side batching**: coalesce N events into one `run_event_batch` message; emit at fixed rate (e.g., 10 Hz)
2. **Client-side dedup**: keep last-N-seen IDs; drop duplicates
3. **Client-side throttle**: use `useSyncExternalStore` with a debounced snapshot
4. **Filtering upstream**: don't emit events the FE doesn't render

## Structured Payload Discipline

```python
# ✅ Good — all payload fields present, types match schema
await sio.emit("gpu_health", {
    "temperature_c": 62.4,
    "utilization_pct": 47,
    "vram_pct": 71.2,
    "power_w": 210,
    "timestamp": now_iso(),
})

# ❌ Bad — missing fields, type drift
await sio.emit("gpu_health", {
    "temp": "62.4",  # string, not float; wrong field name
    "util": 47,
})
```

If a payload changes shape, ALL consumers must be updated in the same commit. Never merge a partial event-shape change.

## Trace / Event Logging

Every emitted event should also be persistable via `bff/services/event_commit_ledger.py`. This gives:

- Historical replay of a run's events
- Debug drilldown for post-mortems
- Data for the future skill-proposal-pipeline (see BACKLOG.md)

Rule: if an event is worth emitting to real-time subscribers, it's worth persisting to the ledger.

## Adding a New Event Type — Complete Checklist

1. **SDK / source of the event**: identify the class name emitted by the agent-server or synthesized by BFF
2. **`bff/services/event_normalize.py`**: add to `_KIND_TO_TYPE`
3. **Test in `bff/tests/`**: unit test that the normalizer projects the new event correctly
4. **`bff/services/event_relay.py`**: emit if it's a new channel; skip if it just flows through `run_event`
5. **`src/lib/schemas/event.ts`**: add the new type to the Zod schema's `type` enum
6. **`src/features/<affected>/EventCard.tsx`** (or equivalent renderer): handle the new type
7. **Playwright spec** (if user-visible): verify it renders in a real run
8. **DEBUG_LOG.md** if this fixed a bug; **BUILD_LOG.md** as a slice entry regardless

## Anti-Patterns

- ❌ Starting BFF with `bff.main:app` (silently disables all Socket.IO)
- ❌ Emitting from a raw path without going through `event_normalize`
- ❌ Adding a new event type without updating the FE Zod schema
- ❌ Dropping unknown fields from `raw` (breaks event-detail drawer)
- ❌ Emitting to `room=None` (broadcasts to everyone, wastes bandwidth)
- ❌ Not cleaning up socket handlers in useEffect return (memory leak)
- ❌ Silently ignoring Zod parse failures on the client (bugs go invisible)
- ❌ High-frequency emits without batching (browser slowdown)
- ❌ Two events for one intent (state gets out of sync)
- ❌ Skipping the DEBUG_LOG search before diagnosing (mandatory per project instructions)

## Cross-References

- `forge-oh-event-normalizer` — the normalization contract in detail
- `bff-router-authoring` — how routers integrate with Socket.IO
- `bff-fe-contract-sync` — Zod schema for events matches Pydantic
- `forge-oh-debug-driver` — DEBUG_LOG search protocol
- `forge-oh-colossus-ops` — verified BFF start command

## Verification Checklist

1. BFF started with `app_with_sio`
2. Browser WS connection is 101 Switching Protocols
3. Server logs show the emit line
4. Browser DevTools WS Messages show the event
5. Zod parses the event without errors
6. Component re-renders with the new data
7. Cleanup handlers run when component unmounts (no leak)
