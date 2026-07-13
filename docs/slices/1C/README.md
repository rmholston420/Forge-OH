# Slice 1C — Plan Rail and Run Controls

## Routes
- `POST /api/runs/:runId/pause`
- `POST /api/runs/:runId/resume`
- `POST /api/runs/:runId/stop`

## PlanNode States
`queued` | `active` | `done` | `failed` | `blocked` | `awaiting-approval`

## States to Handle
- All 6 PlanNode states visually distinct
- Run controls correctly disabled/enabled per run status
- Awaiting-approval banner: amber, full-width, unmissable
- Paused state visually distinct from stopped

## Feature Flag
`NEXT_PUBLIC_FEATURE_PLAN_RAIL_ENABLED`

## Acceptance Criteria
- Controls visible and correctly stateful during streaming
- Plan node statuses update from stream events
- Paused and awaiting-approval states unmissable
