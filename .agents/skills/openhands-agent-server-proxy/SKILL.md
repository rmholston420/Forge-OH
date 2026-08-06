---
name: openhands-agent-server-proxy
description: How to proxy requests from the BFF to the OpenHands agent-server on port 8090 in Forge-OH. Use whenever adding a BFF endpoint that forwards to the agent-server, handling agent-server errors, dealing with connection timeouts, or debugging why an endpoint returns ConnectionError. Covers the forward pattern, timeout budget, error mapping, and the "agent-server is required" test-isolation rule.
license: MIT
triggers:
  - agent-server
  - "agent_server"
  - "127.0.0.1:8090"
  - "port 8090"
  - "openhands.agent_server"
  - "ConnectionError"
  - "httpx.ConnectError"
  - "httpx.ReadTimeout"
  - "trust-remote-code"
  - proxy
  - forward
  - "/api/agent-server"
  - openhands sdk
  - "1.40.0"
---

# OpenHands Agent-Server Proxy in Forge-OH

## Architecture

- **Agent-server**: `openhands.agent_server` from OpenHands SDK 1.40.0, running on `127.0.0.1:8090`
- **Started via**: `.oh-venv/bin/python -m openhands.agent_server` from `~/dev/forge-oh`
- **BFF role**: single-user local-first proxy; forwards specific endpoints, adds Forge-OH-specific state (agent presets, workspaces, trajectories)
- **Direct client access**: none — browser never talks to :8090; only BFF does

## Non-Negotiable Rules

1. **The browser never talks to :8090 directly.** All access goes through :8081 (BFF).
2. **Every proxy endpoint has a timeout budget.** Default 30s for creation, 5s for reads. Never `timeout=None`.
3. **Agent-server errors get MAPPED, not passed through.** A 500 from :8090 → a domain-appropriate error from :8081 (usually 502 Bad Gateway or 500 with a clear detail).
4. **httpx exceptions have empty `__str__` — always include the class name in error logs.** See `bff/services` for the pattern.
5. **Never launch the agent-server in an ad-hoc subprocess.** Use the wrapper scripts (`scripts/forge-up.sh`) or the systemd unit if one exists.

## Verified Agent-Server Startup

```bash
cd ~/dev/forge-oh
.oh-venv/bin/python -m openhands.agent_server \
  --host 127.0.0.1 --port 8090 \
  >~/.forge-oh/agent-server.log 2>&1 &
```

Or via the wrapper: `bash scripts/forge-up.sh` handles this (plus BFF and Next.js).

## Verified Endpoints (as of SDK 1.40.0)

Agent-server 1.40.0 exposes 9 endpoints. Verified endpoints include:

- `POST /api/skills` — list skills; body: `{"load_public":bool, "load_user":bool, "load_project":bool, "load_org":bool}`
- `POST /api/conversation` — create a conversation (agent run)
- `GET /api/conversation/{id}` — conversation state
- `GET /api/conversation/{id}/events` — event history
- Additional endpoints under `/api/conversation/{id}/*` — see agent-server OpenAPI

Always check the live agent-server's `/openapi.json` before assuming a route exists:

```bash
curl -sf http://127.0.0.1:8090/openapi.json | jq '.paths | keys[]'
```

## The Canonical Proxy Pattern

```python
# bff/routers/skills.py — proxying POST /api/skills
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

AGENT_SERVER_URL = "http://127.0.0.1:8090"

router = APIRouter(prefix="/skills", tags=["skills"])


class LoadSkillsRequest(BaseModel):
    load_public: bool = False
    load_user: bool = True
    load_project: bool = True
    load_org: bool = False


@router.post("")
async def list_skills(req: LoadSkillsRequest):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{AGENT_SERVER_URL}/api/skills",
                json=req.model_dump(),
            )
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=502,
                detail=f"agent-server unreachable (ConnectError): {e}",
            )
        except httpx.ReadTimeout as e:
            raise HTTPException(
                status_code=504,
                detail=f"agent-server timeout (ReadTimeout): {e}",
            )

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"agent-server returned {resp.status_code}: {resp.text[:200]}",
        )

    return resp.json()
```

**Notes on this pattern:**
- `httpx.AsyncClient` in a context manager — never a module-level client (connection pooling breaks on FastAPI reload)
- Timeout is explicit and short
- Both `ConnectError` and `ReadTimeout` are caught and mapped to 502/504
- Class name in error message (httpx exceptions have empty `__str__`)
- Never proxy the raw agent-server error text to the browser without sanitizing (could leak paths, secrets)

## Timeout Budget

| Operation | Timeout | Reason |
|---|---|---|
| Read (GET) | 5s | Should be near-instant |
| List skills / conversations | 10s | May scan disk |
| Create conversation | 30s | Includes LLM warm-up on first call |
| SSE stream | none | Long-lived by design |

Never use `timeout=None` for a non-streaming call. If a call needs >30s, something is wrong upstream.

## Error Mapping Table

| Agent-server response | BFF response | Detail |
|---|---|---|
| `ConnectError` (dead) | 502 | "agent-server unreachable (ConnectError): ..." |
| `ReadTimeout` (slow) | 504 | "agent-server timeout (ReadTimeout): ..." |
| 400 (bad input) | 400 | Pass detail through (sanitized) |
| 404 (not found) | 404 | Pass detail through |
| 422 (validation) | 500 | Our input was wrong; log + fix |
| 500 (crash) | 502 | "agent-server returned 500: ..." |

**Rule of thumb**: the browser should never see a raw agent-server error. It sees a BFF-mapped error with a clear detail.

## httpx Exception `__str__` Trap

`httpx.ConnectError` and `httpx.ReadTimeout` override `__str__` to be empty:

```python
try:
    ...
except httpx.ReadTimeout as e:
    logger.error(f"transport error: {e}")  # logs "transport error: " with empty tail!
```

**Fix**: always include the exception class:

```python
logger.error(f"transport error ({type(e).__name__}): {e}")
```

The harness in `openhands_tools_ext/selfeval/harness.py` was patched to do this on 2026-08-03. See DEBUG_LOG.

## Test Isolation Rule

14 tests in `bff/tests/test_mcp_router.py`, `test_observability_router.py`, `test_plugins_router.py` require the agent-server LIVE at :8090. They will fail with `httpx.ConnectError` if run in isolation.

**Rules:**
- Offline / CI runs: deselect these tests (`pytest --deselect ...`)
- Local runs: bring up agent-server first (`bash scripts/forge-up.sh`)
- Do NOT try to mock the agent-server in these tests — the tests exist to catch contract drift, not to be unit tests
- Consider these more like integration tests; run against a live agent-server

## Startup Coordination

The BFF depends on the agent-server. If the BFF starts before the agent-server, some routes will return 502 until :8090 is up.

Options:
1. `forge-up.sh` starts agent-server FIRST, then BFF (with retry on 502)
2. BFF exposes a `/health` endpoint that returns 503 until :8090 responds; front-end shows "connecting..." during that window
3. BFF caches agent-server responses; serves stale on connect error (only for read endpoints)

Currently option 1 is in use. Do not add hard-failure on startup if agent-server is down; log a warning and retry.

## Debugging Connection Failures

Diagnosis order:

1. `curl -sf http://127.0.0.1:8090/openapi.json` — is agent-server responding at all?
2. `ps aux | grep openhands.agent_server` — is it running?
3. `tail -50 ~/.forge-oh/agent-server.log` — did it start cleanly?
4. `curl -sf http://127.0.0.1:8090/api/conversation -X POST -d '{...}'` — does the raw call work?
5. If (4) works but BFF fails, the issue is in the proxy code — check timeout, headers, request body serialization
6. Search DEBUG_LOG.md for similar failure (mandatory per project instructions)

## Anti-Patterns

- ❌ Proxying without a timeout (`httpx.AsyncClient()` with defaults = 5s connect + None read = potentially forever)
- ❌ Passing agent-server errors straight through (leaks internals, confuses users)
- ❌ Using a module-level `httpx.AsyncClient` (breaks on reload)
- ❌ Logging `str(httpx.ConnectError)` — it's empty; always include class name
- ❌ Mocking the agent-server in integration tests (defeats the purpose)
- ❌ Hardcoding `AGENT_SERVER_URL` in every router — centralize in a config module
- ❌ Assuming agent-server endpoints from memory — check `/openapi.json`
- ❌ Not restarting BFF after agent-server upgrade (SDK version drift)

## Cross-References

- `forge-oh-colossus-ops` — how to start/stop agent-server and BFF cleanly
- `forge-oh-debug-driver` — DEBUG_LOG search protocol
- `bff-router-authoring` — general BFF router shape
- `http-api-authoring` (user scope) — HTTP client best practices
- `env-and-secrets-discipline` (user scope) — venv activation for agent-server

## Verification Checklist for a New Proxy Endpoint

1. Timeout set explicitly (never `None` for non-streaming)
2. `httpx.ConnectError` and `httpx.ReadTimeout` caught separately
3. Class name in every logged error message
4. Agent-server error responses mapped to BFF-appropriate status codes
5. Zod schema in `src/lib/schemas/` mirrors the response shape
6. Test covers happy path AND agent-server-down path
7. If the endpoint is required for a page to work, the FE handles 502/504 gracefully (loading state, error boundary)
