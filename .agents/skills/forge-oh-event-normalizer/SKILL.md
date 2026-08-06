---
name: forge-oh-event-normalizer
description: The contract between agent-server SDK events and the Forge-OH wire format defined in bff/services/event_normalize.py. Use whenever adding a new event type, hitting an "unrecognized event kind" warning, changing an existing normalization, or debugging why EventCard renders "unknown". Enforces the _KIND_TO_TYPE dict as source of truth, the raw-passthrough rule, and the SDK-version-drift check.
license: MIT
triggers:
  - event_normalize
  - _KIND_TO_TYPE
  - MessageEvent
  - ActionEvent
  - ObservationEvent
  - AgentErrorEvent
  - ConversationStateUpdateEvent
  - Condensation
  - CondensationSummaryEvent
  - MemoryConsultationEvent
  - WebSearchEvent
  - EventCard
  - "unknown event"
  - "unrecognized event"
  - normalize event
---

# Forge-OH Event Normalizer

The single translation point between richly-typed agent-server SDK events and the flat wire format the frontend consumes.

## The Contract

**Input**: `openhands.sdk.event.*` classes — `MessageEvent`, `ActionEvent`, `ObservationEvent`, `Condensation`, etc.

**Output**: normalized envelope
```json
{
  "id": "evt-...",
  "type": "message",          // from _KIND_TO_TYPE
  "timestamp": "2026-08-06T14:52:03.412Z",
  "source": "agent",
  "summary": "Applied edit to bff/routers/skills.py",
  "raw": { /* the original event, untouched */ }
}
```

**Location**: `bff/services/event_normalize.py`. This is the ONLY place where the SDK-to-wire projection happens. Every emit site calls `normalize(event)` before sending.

## Non-Negotiable Rules

1. **Every SDK event class must appear in `_KIND_TO_TYPE`** or it falls through to `"unknown"`, which the FE renders as a warning card. Do NOT let events fall through — add the mapping.
2. **`raw` is untouched.** Do not filter, rename, or drop fields. The event-detail drawer relies on complete raw payloads.
3. **`type` values are the wire vocabulary — the frontend enum matches this exactly.** Adding a new value here means updating `src/lib/schemas/event.ts` in the same commit.
4. **Multiple SDK classes MAY map to one wire type** (e.g., both `AgentErrorEvent` and `ConversationErrorEvent` → `"error"`).
5. **One SDK class maps to exactly one wire type.** Never conditional-map based on payload.
6. **When SDK versions change, verify the class names still exist.** `CondensationEvent` was renamed to `Condensation` between SDK versions — the mapping had to be updated.

## Current Mapping (as of SDK 1.40.0)

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

## Adding a New Event Type — Full Procedure

### 1. Identify the SDK class name

For SDK-emitted events, find the class in `.oh-venv/lib/python3.12/site-packages/openhands/sdk/event/`. The class name is what appears in the `type(evt).__name__` check.

For BFF-synthesized events (like `MemoryConsultationEvent`, `WebSearchEvent`), define the class in the service that emits them (e.g., `bff/services/memory_events.py`).

### 2. Choose a wire type

Existing wire types:
- `message` — user↔agent conversation
- `action` — agent about to do something
- `observation` — result of an action
- `error` — any error
- `status` — lifecycle / progress / non-critical
- `condensation`, `condensation_request`, `condensation_summary` — context compaction
- `run_paused` — pause markers
- `memory_consultation` — semantic memory lookup
- `web_search` — external web search

If the new event fits an existing bucket, reuse it. If it's genuinely new (e.g., "tool-call-batched"), add a new type.

### 3. Update `_KIND_TO_TYPE`

```python
_KIND_TO_TYPE: dict[str, str] = {
    # ...
    "NewSdkClassName": "new_wire_type",
}
```

Order in the dict: alphabetical within each family, or grouped by SDK version. Match the surrounding style.

### 4. Update `src/lib/schemas/event.ts`

Add the new type to the FE Zod enum:

```typescript
export const EventTypeSchema = z.enum([
  "message",
  "action",
  "observation",
  // ...
  "new_wire_type",   // <— add
]);
```

### 5. Handle it in EventCard (or the relevant renderer)

```tsx
// src/features/runs/EventCard.tsx
function renderByType(event: Event) {
  switch (event.type) {
    case "message": return <MessageCard event={event} />;
    // ...
    case "new_wire_type": return <NewTypeCard event={event} />;
    default: return <UnknownEventCard event={event} />;
  }
}
```

Every wire type needs a renderer. Falling through to `UnknownEventCard` is a bug — the point of adding the mapping was to render it properly.

### 6. Write a unit test

`bff/tests/test_event_normalize.py`:

```python
def test_normalize_new_type():
    raw = {"kind": "NewSdkClassName", "id": "e1", "timestamp": "...", "payload": {...}}
    out = normalize(raw)
    assert out["type"] == "new_wire_type"
    assert out["raw"] == raw
```

### 7. Log to DEBUG_LOG.md IF this was a bug fix, or BUILD_LOG.md IF this was a feature slice

## When the SDK Changes

Every time the OpenHands SDK is upgraded on Colossus, run this check:

```bash
cd ~/dev/forge-oh
grep -oE '"[A-Z][A-Za-z]+Event"' bff/services/event_normalize.py | sort -u > /tmp/normalize_classes.txt
grep -rho 'class [A-Z][A-Za-z]*Event' .oh-venv/lib/python*/site-packages/openhands/sdk/event/ | sort -u > /tmp/sdk_classes.txt
diff /tmp/normalize_classes.txt /tmp/sdk_classes.txt
```

- Classes in normalizer but not in SDK → deleted upstream; check for renamings
- Classes in SDK but not in normalizer → new events we don't yet handle

Historical example: `CondensationEvent` (old) was renamed to `Condensation` (new). The normalizer's mapping had to change or events fell through to `"unknown"`.

## Payload Consistency Rules

Wire event fields:

- **`id`**: unique per event; use the SDK's event ID if present, otherwise generate a UUID
- **`type`**: from `_KIND_TO_TYPE`; NEVER derive at runtime from anything else
- **`timestamp`**: ISO-8601 UTC string; convert from `datetime` if SDK provides that
- **`source`**: one of `"agent"`, `"user"`, `"system"`, `"tool"` — never freeform
- **`summary`**: pre-rendered, ≤ 200 chars; used for card previews. Truncate long text.
- **`raw`**: everything the SDK gave us, untouched

## Summary Rendering Discipline

The `summary` field is what the FE shows in the run's timeline card. Rules:

- Max 200 chars — truncate with ellipsis
- Plain text, no markdown (the drawer handles rich rendering)
- Verb-first when it makes sense: "Edited bff/routers/skills.py", "Read src/lib/schemas/event.ts"
- Show the domain-relevant field: for an ActionEvent this is the tool + target; for a MessageEvent it's the first line

Bad summary: `"ObservationEvent id=abc-123 tool_output=<long-json>"`
Good summary: `"grep found 47 matches in bff/"`

## Debugging Fallthroughs

Symptom: FE shows an `UnknownEventCard` in the timeline.

Diagnosis:

1. Open browser DevTools → filter Socket.IO messages for the run
2. Find the event with `type: "unknown"` — read the raw kind
3. Match the kind against `_KIND_TO_TYPE` in `event_normalize.py`
4. If missing, follow the "Adding a New Event Type" procedure above
5. Log to DEBUG_LOG.md

## Anti-Patterns

- ❌ Adding to `_KIND_TO_TYPE` without updating the FE enum in the same commit
- ❌ Filtering fields from `raw` (breaks event-detail drawer)
- ❌ Runtime-conditional mapping (one class = one wire type, always)
- ❌ New wire type without a matching EventCard renderer (fallthrough to unknown)
- ❌ Not testing new mappings
- ❌ Long unstructured summaries (should be ≤ 200 chars, semantically dense)
- ❌ Skipping the SDK-version-drift check after an upgrade
- ❌ Dropping SDK class name changes (rename in SDK = rename in normalizer)
- ❌ Skipping DEBUG_LOG search before investigating a normalization bug (mandatory per project instructions)

## Cross-References

- `socketio-events-tracing` — how events flow from BFF to browser
- `bff-fe-contract-sync` — Zod schema for events matches Pydantic
- `forge-oh-repo-navigation` — where event-related files live
- `bff-router-authoring` — routers that serve events

## Checklist for Every New Event Type

1. SDK class name identified (or newly defined for BFF events)
2. `_KIND_TO_TYPE` updated in `bff/services/event_normalize.py`
3. `EventTypeSchema` enum updated in `src/lib/schemas/event.ts`
4. `EventCard` (or the relevant renderer) has a case for the new type
5. Unit test in `bff/tests/test_event_normalize.py` covers the mapping
6. Playwright spec (if user-visible) verifies rendering
7. `raw` remains untouched by the projection
8. Summary is ≤ 200 chars, verb-first when possible
9. Docs updated if a new wire vocabulary was added
10. BUILD_LOG.md or DEBUG_LOG.md entry appended
