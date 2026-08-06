---
name: fastapi-router-authoring
description: Idioms and hazards for authoring FastAPI routers. Use whenever adding a new endpoint, using APIRouter, wiring dependencies, defining request/response models, or debugging FastAPI-specific errors (Depends cycles, path-order gotchas, response validation). Covers Pydantic v2 alignment, async correctness, dependency injection, and OpenAPI hygiene.
license: MIT
triggers:
  - FastAPI
  - APIRouter
  - Depends
  - response_model
  - HTTPException
  - "@router"
  - include_router
  - Pydantic
  - BaseModel
  - Field
  - "async def"
---

# FastAPI Router Authoring

Applies to any FastAPI codebase, Python 3.11+, Pydantic v2.

## APIRouter Prefix — One Owner Rule

A prefix can be set in TWO places. Pick one owner per router:

```python
# Option A: on the router (preferred for standalone routers)
router = APIRouter(prefix="/skills", tags=["skills"])
app.include_router(router, prefix="/api")   # final: /api/skills

# Option B: on the include (preferred when the router is generic and reused)
router = APIRouter(tags=["skills"])
app.include_router(router, prefix="/api/skills")   # final: /api/skills
```

**Never** set the prefix in both:

```python
# ❌ Final path becomes /api/skills/skills — double prefix
router = APIRouter(prefix="/skills")
app.include_router(router, prefix="/api/skills")
```

Convention I use: prefix on the router (`/skills`), `/api` on the include. Keeps routers portable and predictable.

## Path Order Matters

FastAPI matches paths in registration order:

```python
# ❌ /users/me will NEVER match — /users/{user_id} caught it first
@router.get("/users/{user_id}")
def get_user(user_id: str): ...

@router.get("/users/me")
def get_me(): ...

# ✅ Specific paths before parametric paths
@router.get("/users/me")
def get_me(): ...

@router.get("/users/{user_id}")
def get_user(user_id: str): ...
```

Rule: put **specific** paths before **parametric** paths within a router.

## Async vs Sync — The Blocking Trap

FastAPI runs `async def` endpoints on the event loop. Blocking I/O inside an `async def` freezes the loop:

```python
# ❌ Blocking call in async endpoint — freezes the entire server for the duration
@router.get("/data")
async def get_data():
    result = requests.get("http://upstream")   # blocking!
    return result.json()

# ✅ Use an async client
@router.get("/data")
async def get_data():
    async with httpx.AsyncClient() as client:
        result = await client.get("http://upstream")
    return result.json()

# ✅ Or make the endpoint sync (FastAPI runs it in a threadpool)
@router.get("/data")
def get_data():
    result = requests.get("http://upstream")
    return result.json()
```

Rule of thumb: `async def` only when EVERY I/O call inside is `await`ed. If you have to mix, make the endpoint `def` (sync) and let FastAPI's threadpool handle it.

## Request / Response Models

Every endpoint declares typed request and response:

```python
class SkillOut(BaseModel):
    name: str
    description: str
    triggers: list[str]

    model_config = ConfigDict(extra="forbid")   # unknown fields → 422

class SkillListResponse(BaseModel):
    data: list[SkillOut]
    total: int

@router.get("/", response_model=SkillListResponse)
async def list_skills() -> SkillListResponse:
    return SkillListResponse(data=[...], total=42)
```

Why both `-> SkillListResponse` and `response_model=`?

- The return annotation is for type checkers and IDE support
- `response_model=` is what FastAPI uses to filter the response and generate OpenAPI

They should match. If they don't, `response_model=` wins at runtime.

**When `response_model` differs from the return type**: usually to hide fields (e.g., password_hash). Prefer separate `-In` / `-Out` models over `response_model_exclude`.

## Dependency Injection — Depends()

Depends is FastAPI's DI system. Common uses:

```python
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    ...

@router.get("/me")
async def read_me(user: User = Depends(get_current_user)):
    return user
```

Rules:
- Dependencies with `yield` behave like context managers (setup / teardown)
- Dependencies are cached per-request — `Depends(get_db)` in three places = one call
- Avoid dependency cycles (A depends on B depends on A) — FastAPI won't detect them, you get RecursionError at request time

## HTTPException

```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="skill not found")

# With extra headers
raise HTTPException(
    status_code=401,
    detail="not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)
```

Never `return {"error": "..."}` with status 200 to signal an error. Raise HTTPException with the right code.

## Pydantic v2 Highlights

Pydantic v1 → v2 broke many things. Common patterns:

```python
# ✅ v2
class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # was: orm_mode
    name: str = Field(..., min_length=1)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def check_something(self):
        if len(self.name) > 100:
            raise ValueError("too long")
        return self
```

Deprecated in v2 (still work but warn):
- `@validator` → `@field_validator`
- `@root_validator` → `@model_validator`
- `Config` inner class → `model_config = ConfigDict(...)`
- `.dict()` → `.model_dump()`
- `.json()` → `.model_dump_json()`
- `orm_mode` → `from_attributes`

## OpenAPI Docs Hygiene

- Add `tags=["..."]` to every router — groups endpoints in Swagger UI
- Add a `summary` and (long-form) `description` to every endpoint
- Declare error responses:

```python
@router.get(
    "/skills/{name}",
    response_model=SkillOut,
    responses={
        404: {"description": "Skill not found"},
        502: {"description": "Agent-server unreachable"},
    },
)
async def get_skill(name: str) -> SkillOut: ...
```

Free docs at `/docs` (Swagger UI) and `/redoc`. Free typed clients via `openapi-typescript`.

## Common Failure Modes

### `422 Unprocessable Entity` on every request

Request model doesn't match the client's payload shape. Read the response body — FastAPI returns the exact field paths that failed. If the payload looks right, check for field-name mismatches (`user_id` vs `userId`).

### `500 Internal Server Error` with no traceback

Response failed to serialize. Usually: `response_model` has a required field the actual return dict is missing. Enable debug logs or add `logfire` / `structlog` to catch the ValidationError.

### `RuntimeError: This event loop is already running`

Called `asyncio.run(...)` inside an already-running loop. Never do that inside an endpoint. Use `await` directly.

### Endpoint hangs forever

Blocking I/O inside `async def`. See "Async vs Sync" above.

### Circular import between routers

Extract shared models to a `schemas.py` module. Routers import from schemas; schemas import from nothing app-specific.

## Anti-Patterns

- ❌ `async def` with `time.sleep()` / `requests.get()` / any blocking call
- ❌ Same prefix declared on router AND include
- ❌ Parametric path registered before specific path
- ❌ `return {"error": "..."}` with status 200
- ❌ `response_model` and return type disagreeing on required fields
- ❌ Using v1 Pydantic patterns in a v2 codebase (silent deprecation warnings)
- ❌ Global mutable state (module-level dicts modified per-request)
- ❌ Passing `Request` around instead of using `Depends` for injection

## Checklist for a New Router

1. Prefix owner decided (router vs include)
2. `tags=[...]` set
3. Request models with `extra="forbid"`
4. Response models with matching return annotation
5. Path order: specific before parametric
6. Async correctness: no blocking calls in `async def`
7. Dependencies via `Depends`, not module globals
8. HTTPException for 4xx/5xx, not `return {"error": ...}`
9. `responses={}` documents error statuses
10. Registered in `main.py` with the right include prefix
11. pytest smoke test: happy path + one 4xx + one 5xx
