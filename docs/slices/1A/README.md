# Slice 1A — Runs Home and Launcher

## Routes
- `GET /api/runs` — list runs (query: `status`, `workspaceId`, `search`, `page`)
- `POST /api/runs` — create run
- `GET /api/agents/presets` — list agent presets
- `GET /api/workspaces` — list workspaces

## Request / Response Shapes

### `GET /api/runs` response
```json
{
  "data": [
    {
      "id": "run_001",
      "title": "Refactor auth module",
      "status": "running",
      "agentPresetName": "DevstralAgentic",
      "workspaceId": "ws_001",
      "workspaceType": "docker",
      "activeTool": "file_editor",
      "updatedAt": "2026-07-13T04:00:00Z",
      "createdAt": "2026-07-13T03:45:00Z",
      "elapsedMs": 900000,
      "estimatedCostUsd": 0.042
    }
  ],
  "pageInfo": { "total": 1, "page": 1, "pageSize": 20 }
}
```

### `POST /api/runs` request
```json
{
  "title": "string",
  "prompt": "string",
  "agentPresetId": "string",
  "workspaceId": "string"
}
```

## States to Handle
- Loading skeleton (runs list)
- Empty state (no runs yet)
- Error state (BFF unreachable)
- Disabled state (no workspaces available)
- Optimistic new run immediately in list

## Feature Flag
`NEXT_PUBLIC_FEATURE_RUNS_HOME_ENABLED`

## Acceptance Criteria
- User can launch a run from the home screen
- New run appears with optimistic state, updates after backend confirmation
- Run creation disabled when no workspace available
