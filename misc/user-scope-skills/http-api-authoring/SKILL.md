---
name: http-api-authoring
description: HTTP/REST API authoring discipline — idempotency, status codes, error-shape consistency, pagination, versioning. Use when adding a new endpoint, choosing a status code, designing an error response, exposing a list endpoint, or wrapping a proxy. Applies to FastAPI, Flask, Express, or any HTTP framework.
license: MIT
triggers:
  - REST API
  - endpoint
  - route
  - FastAPI
  - HTTPException
  - status code
  - "502"
  - "404"
  - pagination
  - idempotency
  - OpenAPI
  - proxy
---

# HTTP API Authoring

## Status Codes — Pick the Right One

| Range | Meaning | Common members |
|---|---|---|
| 2xx | Success | 200 OK, 201 Created (with `Location:`), 204 No Content |
| 3xx | Redirect | 301 permanent, 302 temporary, 304 not modified |
| 4xx | Client error | 400 bad input, 401 unauthenticated, 403 unauthorized, 404 not found, 409 conflict, 422 validation, 429 rate limit |
| 5xx | Server error | 500 unexpected, 502 upstream failed, 503 unavailable, 504 upstream timeout |

Rules:

- **401 vs 403**: 401 means "I don't know who you are, log in." 403 means "I know who you are, you can't do this."
- **400 vs 422**: 400 for malformed request (bad JSON, missing header). 422 for well-formed input that fails validation (email format, out-of-range number).
- **404 vs 403**: If the resource exists but the user can't access it, prefer 404 (avoids leaking existence).
- **502 vs 500**: 502 when a downstream service you called failed. 500 when *your* code raised an unexpected exception.
- **204 vs 200 with `null` body**: 204 if there's genuinely no body. 200 with `{}` or `{"success": true}` is common for delete endpoints.

## Idempotency

An operation is idempotent if calling it N times has the same effect as calling it once.

- `GET` — MUST be idempotent (also safe, i.e., no side effects)
- `PUT` — MUST be idempotent (`PUT /users/42` with the same body twice = one user)
- `DELETE` — MUST be idempotent (second DELETE returns 404 or 204, not 500)
- `POST` — NOT required to be idempotent. Use it for create-with-server-generated-id.
- `PATCH` — usually idempotent; verify per endpoint.

**When POST needs to be idempotent** (e.g., payment processing), require an `Idempotency-Key` header from the client and dedupe server-side.

## Error Response Shape — Be Consistent

Pick ONE error shape for the whole API and stick to it. FastAPI's default:

```json
{"detail": "human message"}
```

or with more context:

```json
{
  "detail": "human message",
  "error_code": "SKILL_NOT_FOUND",
  "field": "name"
}
```

Do NOT mix shapes. If some endpoints return `{"error": "..."}` and others return `{"detail": "..."}`, every client integration has to branch on both. Pick one, document it, enforce it in tests.

## Proxy Endpoint Pattern

When your service proxies an upstream:

```python
try:
    resp = await client.post("/upstream/api", json=body)
except httpx.ConnectError as exc:
    # Network / DNS / connection refused — upstream is down
    raise HTTPException(status_code=502, detail=f"upstream unreachable: {exc}") from exc
except httpx.TimeoutException as exc:
    raise HTTPException(status_code=504, detail=f"upstream timeout: {exc}") from exc

if resp.status_code >= 400:
    # Upstream returned an HTTP error
    raise HTTPException(
        status_code=502,
        detail=f"upstream error {resp.status_code}: {resp.text[:200]}"
    )
```

Never surface a raw upstream error body — sanitize it, cap the length, and always wrap the status. A client should be able to trust that a 4xx from your API means *they* did something wrong.

## Pagination

For any list endpoint that could return more than 100 items, paginate. Two common shapes:

**Offset/limit** — simple, but breaks if the underlying data changes mid-scroll:

```
GET /runs?limit=50&offset=100
→ {"data": [...], "total": 4200}
```

**Cursor-based** — stable during pagination, harder to jump to a page:

```
GET /runs?limit=50&cursor=eyJpZCI6IjEyMyJ9
→ {"data": [...], "next_cursor": "eyJpZCI6IjE3MyJ9"}
```

Cursor for feeds and event streams. Offset for admin dashboards.

## Field Naming

- Pick one convention (`snake_case` OR `camelCase`) and enforce it across the whole API surface.
- If the frontend needs camelCase and the backend uses snake_case, transform at the client's API layer — NOT in the response middleware. Middleware transforms are invisible and fight OpenAPI generation.

## Versioning

- URI versioning (`/v1/...`, `/v2/...`) is the least surprising. Header versioning is more elegant on paper, harder in practice.
- Keep the version until you have zero clients on the old one.
- Never "silently" change response shape on an unversioned endpoint. That's not a fix — it's a broken contract.

## OpenAPI / Docs

- Every response body has a Pydantic/typed schema. FastAPI generates OpenAPI from these — free API docs and typed clients.
- Every error status code in production behavior is declared: `responses={502: {"description": "..."}, 404: {...}}`.
- If you're using Pydantic v2, prefer `model_config = ConfigDict(extra="forbid")` on request models — rejects unknown fields loudly instead of silently ignoring them.

## Anti-Patterns

- ❌ Returning 200 with `{"error": "..."}` (200 must mean success)
- ❌ Different error shapes across endpoints in the same API
- ❌ Surfacing raw upstream errors to your clients
- ❌ Making DELETE non-idempotent (500 on second call)
- ❌ Missing pagination on a list endpoint that could grow
- ❌ Using POST to fetch data (breaks HTTP caching, browser history, and semantic sense)
- ❌ 500 for user error (should be 4xx)
- ❌ 404 when you mean 401/403 in a public API (in a private/internal API 404 is fine to avoid enumeration)

## Adding a New Endpoint — Checklist

1. Method matches the semantics (GET for read, POST for create, PUT for replace, PATCH for partial update, DELETE for remove)
2. URL is noun-based (`/runs`, `/runs/{id}/events`) not verb-based (`/getRuns`)
3. Request body has a typed schema
4. Response body has a typed schema
5. Error cases have explicit status codes
6. Auth requirement is enforced
7. Pagination if the response can grow
8. Test: happy path (200), one 4xx client error case, one 5xx upstream error case
