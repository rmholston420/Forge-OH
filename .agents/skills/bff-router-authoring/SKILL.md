---
name: bff-router-authoring
description: How to author a new BFF FastAPI router in Forge-OH — matching the shape of agent_presets.py, runs.py, skills.py. Use whenever adding a new endpoint under /api/, creating a new bff/routers/*.py file, registering a router in bff/main.py, or debugging why an endpoint 404s. Covers router prefix conventions, Pydantic model naming, error-response patterns, and registration in main.py.
license: MIT
triggers:
  - "bff/routers/"
  - APIRouter
  - "bff.main"
  - "app_with_sio"
  - CreateRequest
  - "prefix=\"/"
  - "tags=["
  - HTTPException
  - "/api/"
  - forge-oh router
  - agent-presets
  - "ap-1"
---

# Forge-OH BFF Router Authoring

Applies to any new or modified router under `bff/routers/`.

## Canonical Structure — copy from `agent_presets.py` or `runs.py`

```python
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/<resource-plural>", tags=["<resource-plural>"])
```

**Rules:**
- Prefix is `/<resource-plural>` — no `/api` here (that's added when mounted in `bff/main.py`)
- Prefix is kebab-case: `/agent-presets`, `/self-eval`, `/inference-backends`
- Tags match the prefix (used by FastAPI's `/docs`)
- One router file per resource; do NOT combine multiple resources in one file

## Naming Conventions

| Item | Convention | Example |
|---|---|---|
| File | snake_case, plural | `agent_presets.py`, `runs.py` |
| Router prefix | kebab-case, plural | `/agent-presets`, `/runs` |
| ID prefix | short kebab | `ap-1` (agent-preset), `r-<uuid>` (run) |
| Response model | PascalCase entity name | `AgentPreset`, `Run`, `Skill` |
| Create request | `CreateRequest` | (nested in same file) |
| Update request | `UpdateRequest` | (nested in same file) |
| List response | `List<Entity>Response` | `ListAgentPresetsResponse` |

## Pydantic Model Discipline

```python
class AgentPreset(BaseModel):
    id: str
    name: str
    description: str | None = None
    # ISO-8601 UTC strings — NEVER datetime objects on the wire
    createdAt: str
    updatedAt: str
```

**Rules:**
- Field names: camelCase (frontend consumes them directly)
- Timestamps: ISO-8601 strings, not `datetime` — front-end converts
- Optional fields: `str | None = None` (PEP 604 union), never `Optional[str]`
- Lists default via `Field(default_factory=list)`, never `= []`
- Enums: `Literal[...]` when values are stable; `str` when they're free-form (see agent_presets.py's `ModelId` comment)

## Response Envelope

Two patterns exist in the codebase:

### Pattern A — direct entity (single-item endpoints)

```python
@router.get("/{preset_id}")
def get_preset(preset_id: str) -> AgentPreset:
    ...
```

### Pattern B — `data` envelope (list endpoints)

```python
class ListAgentPresetsResponse(BaseModel):
    data: list[AgentPreset]
    total: int

@router.get("")
def list_presets() -> ListAgentPresetsResponse:
    ...
```

**Rule:** if the FE consumer needs pagination or metadata, use the `data` envelope. If it's a raw entity or a raw list, return it directly. Match existing patterns for the resource family.

## Errors

Always raise `HTTPException` with a `detail` string:

```python
if not preset:
    raise HTTPException(status_code=404, detail=f"Agent preset {preset_id} not found")
```

**Rules:**
- Never return `{"error": "..."}` — always use `HTTPException`
- Status codes: 400 (bad request), 404 (not found), 409 (conflict), 422 (validation, FastAPI handles automatically), 500 (unexpected)
- `detail` is a string, not a dict, unless you have a good reason
- Never leak internal exception messages in production paths — wrap with `except Exception as e: raise HTTPException(500, "internal error")` in critical routes

## Registration in `bff/main.py`

After creating the router:

```python
# bff/main.py
from bff.routers import skills  # add import

# ...

app.include_router(skills.router, prefix="/api")  # add include
```

**Rules:**
- Mount under `/api` prefix from `main.py` (individual routers don't include `/api` in their own prefix)
- Add the import alphabetically to the router imports block
- Add the include at the same location as other includes
- If the entrypoint is `app_with_sio` (Socket.IO wrapper), the include happens on `app` before wrapping — verify `app_with_sio` exports the same routes

## Idempotency

For any POST that creates a resource, follow the pattern in `bff/services/idempotency_ledger.py`:

- Accept an `Idempotency-Key` header
- Cache the response by key for N minutes
- Re-POST with the same key returns the cached response, not a duplicate resource

Not every endpoint needs this. Rule of thumb: any create that would be bad to duplicate → idempotency-key.

## Streaming

For SSE endpoints (e.g., `/runs/{id}/events/stream`):

```python
from starlette.responses import StreamingResponse

@router.get("/{run_id}/events/stream")
def stream_events(run_id: str):
    async def event_gen():
        async for event in event_relay.stream(run_id):
            yield f"data: {event.model_dump_json()}\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

Rules:
- Return `StreamingResponse`, not `Response`
- Media type `text/event-stream` for SSE
- Format: `data: <json>\n\n` — the double newline is required
- Emit heartbeat comments (`: keepalive\n\n`) every 15s or the connection times out

## Testing

Every new router needs `bff/tests/test_<router>_router.py`:

```python
from fastapi.testclient import TestClient
from bff.main import app

client = TestClient(app)

def test_list_returns_default():
    resp = client.get("/api/agent-presets")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert any(p["isDefault"] for p in data["data"])
```

- One test per endpoint, minimum
- Test happy path AND error path (404, 422)
- Use `TestClient(app)`, NOT the network — no live BFF needed
- Fixtures for state go in `bff/tests/conftest.py`

## Verification After Landing

1. `pytest bff/tests/test_<router>_router.py` — passes
2. Restart BFF: `bash scripts/forge-restart.sh --bff-only`
3. `curl -sf http://127.0.0.1:8081/api/<resource>` — returns 200
4. `curl -sf http://127.0.0.1:8081/docs` — router appears in Swagger
5. `curl -sf http://127.0.0.1:8081/openapi.json | jq '.paths | keys[] | select(startswith("/<resource>"))'` — endpoints listed

## Common Failure Modes

### Endpoint returns 404 in production but works in tests

- Router imported but not `include_router`'d in `bff/main.py`
- Prefix double-included: router has `prefix="/api/foo"` AND main.py adds `prefix="/api"` → path becomes `/api/api/foo`
- App-with-sio wrapper not re-including the router — verify `app_with_sio` mounts the same routes

### 422 on every request

- Pydantic model field name mismatch (client sends `agent_preset_id`, model expects `agentPresetId`)
- Missing required field — check the Pydantic error message

### Test fixtures leak between tests

- State (in-memory dicts, module-level lists) persists across tests → use function-scoped fixtures that reset state, or use `dependency_overrides`

### Wrong content type on POST

- Client sends `application/x-www-form-urlencoded`, endpoint expects JSON → FastAPI raises 422

## Anti-Patterns

- ❌ Router prefix includes `/api` (main.py adds it)
- ❌ Snake_case field names in Pydantic response models (breaks FE consumers expecting camelCase)
- ❌ `datetime` objects on the wire (use ISO-8601 strings)
- ❌ `= []` for list defaults (mutable default gotcha)
- ❌ `return {"error": "..."}` instead of `raise HTTPException`
- ❌ Router file with 20 endpoints (split by resource)
- ❌ Untested endpoints (every endpoint needs a test)
- ❌ Adding a router to `bff/routers/` but forgetting `include_router` in `main.py`
- ❌ Using `Optional[str]` instead of `str | None` (codebase uses PEP 604 syntax)
- ❌ Blocking calls (`requests`, `time.sleep`) in async endpoints — use `httpx.AsyncClient` and `asyncio.sleep`

## Cross-References

- `fastapi-router-authoring` (user scope) — general FastAPI patterns
- `bff-fe-contract-sync` — when the FE schema `src/lib/schemas/<x>.ts` and the BFF model diverge
- `forge-oh-repo-navigation` — where to find similar routers to copy from
- `forge-oh-colossus-ops` — how to restart the BFF to pick up your changes
