# Slice 1B — Run Detail with Event Timeline

## Routes
- `GET /api/runs/:runId` — run metadata
- `GET /api/runs/:runId/events` — bootstrap event history
- `WS /runs/:runId/stream` — Socket.IO with `oh-event` messages

## Socket.IO Message Shape (`oh-event`)
```json
{
  "id": 42,
  "runId": "run_001",
  "type": "FileEditAction | CmdRunAction | BrowseInteractiveAction | ...",
  "source": "agent | user",
  "message": "string",
  "timestamp": "2026-07-13T04:00:00Z",
  "extras": {}
}
```

## Streaming Flow
1. Load metadata + bootstrap event history over HTTP
2. Connect Socket.IO with `conversationId` + `latestEventId`
3. Receive `oh-event` → validate → normalize → patch timeline + run status
4. On disconnect: reconnect with latest known `eventId` to avoid duplicates

## States to Handle
- Loading (metadata + events)
- Streaming (banner: Streaming)
- Disconnected (banner: Disconnected + Reconnecting)
- Empty timeline
- Selected event → inspector populated

## Feature Flag
`NEXT_PUBLIC_FEATURE_RUN_DETAIL_ENABLED`
