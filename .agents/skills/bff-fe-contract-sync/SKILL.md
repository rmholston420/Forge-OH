---
name: bff-fe-contract-sync
description: How to keep the BFF Pydantic models and the frontend Zod schemas + endpoint constants in sync in Forge-OH. Use whenever adding a new endpoint, changing a Pydantic response model, updating src/lib/schemas/*.ts, or debugging a "types don't match" error where the browser gets data the FE schema rejects. Enforces the three-file update pattern (router → schema → endpoints registry) and catches drift early.
license: MIT
triggers:
  - "src/lib/schemas/"
  - "src/lib/api/endpoints"
  - z.object
  - "z.infer"
  - "zod"
  - schema mismatch
  - "Invalid response"
  - useQuery
  - fetchJson
  - endpoints.ts
  - "bff/routers/"
  - CreateRequest
---

# BFF ↔ Frontend Contract Sync

Any endpoint change requires updates in **three** places, in this order:

1. **`bff/routers/<x>.py`** — BFF Pydantic model (source of truth)
2. **`src/lib/schemas/<x>.ts`** — Zod schema (FE mirror)
3. **`src/lib/api/endpoints.ts`** — FE endpoint constant registry

Skip any one and something breaks silently or loudly.

## The Contract

```
BFF Pydantic ──► JSON on the wire ──► Zod parse ──► TypeScript type ──► React component
```

**When Pydantic changes, Zod must change.** Zod parse failures are logged at runtime but don't always crash — the component just gets undefined data and breaks in weird ways.

## Canonical Zod Schema Shape

```typescript
// src/lib/schemas/agent-preset.ts
import { z } from "zod";

export const AgentPresetSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  model: z.string(),
  isDefault: z.boolean(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type AgentPreset = z.infer<typeof AgentPresetSchema>;

export const ListAgentPresetsResponseSchema = z.object({
  data: z.array(AgentPresetSchema),
  total: z.number(),
});

export type ListAgentPresetsResponse = z.infer<typeof ListAgentPresetsResponseSchema>;
```

**Rules:**
- File named after resource: `agent-preset.ts`, `run.ts`, `skill.ts`
- Schema exported as `<Name>Schema`; inferred type exported as `<Name>` (without `Schema` suffix)
- Nullable + optional fields: `.nullable().optional()` — matches Pydantic's `str | None = None`
- Timestamps: `z.string()` — the BFF sends ISO-8601 strings
- Enums: `z.enum([...])` matching the Pydantic `Literal[...]` exactly
- Never `z.any()` in a response schema — that defeats validation

## Type Mapping Cheat Sheet

| Pydantic | Zod |
|---|---|
| `str` | `z.string()` |
| `str \| None = None` | `z.string().nullable().optional()` |
| `int` | `z.number()` (or `z.number().int()` if strict) |
| `float` | `z.number()` |
| `bool` | `z.boolean()` |
| `list[X]` | `z.array(XSchema)` |
| `dict[str, X]` | `z.record(z.string(), XSchema)` |
| `Literal["a", "b"]` | `z.enum(["a", "b"])` |
| `datetime` (as ISO string) | `z.string()` |
| Nested `BaseModel` | Nested `z.object({...})` |
| `Any` | `z.unknown()` — never `z.any()` in a validated boundary |

## Field Naming — camelCase Everywhere

BFF Pydantic already uses camelCase for wire fields (see `agent_presets.py` — `isDefault`, `createdAt`, `topP`). Zod matches directly:

```typescript
// ✅ Match wire format exactly
isDefault: z.boolean(),
createdAt: z.string(),
topP: z.number(),

// ❌ Convert to snake_case (wire is camelCase, this would fail parse)
is_default: z.boolean(),
```

## Endpoints Registry Pattern

`src/lib/api/endpoints.ts`:

```typescript
export const ENDPOINTS = {
  // ...
  AGENT_PRESETS: {
    LIST: `/api/agent-presets`,
    GET: (id: string) => `/api/agent-presets/${id}`,
    CREATE: `/api/agent-presets`,
    UPDATE: (id: string) => `/api/agent-presets/${id}`,
    DELETE: (id: string) => `/api/agent-presets/${id}`,
  },
  SKILLS: {
    LIST: `/api/skills`,
    // ...
  },
} as const;
```

**Rules:**
- ONE constant block per resource (UPPER_SNAKE_CASE)
- Static paths: string literal
- Dynamic paths: arrow function taking id/params, returning string
- Always include the `/api` prefix (BFF mounts routers at `/api`)
- `as const` at the end — makes types precise
- Never hardcode a path in a component; always import from `ENDPOINTS.*`

## React Query + Zod — Canonical Pattern

```typescript
// src/features/agent-presets/api.ts
import { useQuery } from "@tanstack/react-query";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { fetchJson } from "@/lib/api/http";
import { ListAgentPresetsResponseSchema } from "@/lib/schemas/agent-preset";

export function useAgentPresets() {
  return useQuery({
    queryKey: ["agent-presets"],
    queryFn: async () => {
      const raw = await fetchJson(ENDPOINTS.AGENT_PRESETS.LIST);
      return ListAgentPresetsResponseSchema.parse(raw);
    },
  });
}
```

`fetchJson` is the shared wrapper in `src/lib/api/http/` — do not use raw `fetch` in feature code.

Zod's `.parse()` throws on mismatch; the ErrorBoundary catches. Use `.safeParse()` if you want to log and fall back.

## The Three-File Update Checklist

When adding a new endpoint:

1. **`bff/routers/<name>.py`** — write router with response models
2. **Restart BFF** — verify endpoint returns expected shape via curl:
   ```bash
   curl -sf http://127.0.0.1:8081/api/<resource> | jq
   ```
3. **`src/lib/schemas/<name>.ts`** — write Zod schemas mirroring the Pydantic models
4. **`src/lib/api/endpoints.ts`** — add the ENDPOINTS block
5. **Feature hook `src/features/<name>/api.ts`** — useQuery + parse
6. **Component** — render the data

**Skip any of 3–5 and the FE either doesn't compile or renders undefined.**

## Common Mismatch Modes

### "Invalid response: expected object, received null"

- BFF returned 200 with null body, or 204 (no content) instead of 200 + `{}`
- Fix: BFF endpoint should return an empty object/list, not null. Or FE should call `.optional()`.

### "Unrecognized key(s): 'foo'"

- BFF added a field, Zod schema doesn't have it
- Zod is strict by default — unknown keys cause `.parse()` to fail
- Fix: add the field to the Zod schema (with `.optional()` if newly-added), OR use `.passthrough()` on the object (not recommended for validated boundaries)

### "Expected string, received null" on createdAt

- BFF sent `null` for a required field
- Fix: BFF should send ISO-8601 string, or FE schema should be `.nullable()`

### The FE builds fine but runtime data is undefined

- Zod parse failed silently — check the browser console for the schema error
- Or the request path is wrong (typo in `endpoints.ts` doesn't fail build)
- Or the BFF route isn't registered (see `bff-router-authoring`)

### Types are wrong in Storybook / test fixtures but right in prod

- Handwritten mock objects diverged from the schema
- Fix: generate mocks from `<Schema>.parse(realResponseFixture)` so the compiler catches drift

## OpenAPI-Driven Sync (Optional)

BFF FastAPI exposes `/openapi.json`. You COULD auto-generate Zod schemas from it (e.g., via `openapi-zod-client`). Currently we hand-write for control, but if drift becomes common, revisit.

## Anti-Patterns

- ❌ Editing `bff/routers/*.py` and NOT updating `src/lib/schemas/*.ts` (silent runtime break)
- ❌ Editing `src/lib/schemas/*.ts` and NOT updating the router (schema now doesn't match reality)
- ❌ Hardcoding paths in components instead of `ENDPOINTS.*`
- ❌ `z.any()` in response schemas (defeats the point)
- ❌ Missing `as const` on ENDPOINTS (loses type precision)
- ❌ snake_case field names in Zod (wire is camelCase)
- ❌ `Optional[str]` in Pydantic but not `.nullable().optional()` in Zod (parse fails on null)
- ❌ Naming inconsistency — `AgentPreset` in Pydantic, `Preset` in Zod (search-and-replace confusion)
- ❌ Two schemas for the same entity (one in `schemas/`, one hand-written elsewhere)

## Cross-References

- `bff-router-authoring` — the BFF half of the contract
- `web-frontend-authoring` (user scope) — React Query patterns
- `http-api-authoring` (user scope) — general contract discipline
- `playwright-forge-oh` — how to verify the sync end-to-end via a visual test

## Checklist for Every Endpoint Change

1. Pydantic model updated in `bff/routers/`
2. BFF restarted (`bash scripts/forge-restart.sh --bff-only`)
3. Endpoint verified via curl → shape matches Pydantic
4. Zod schema updated in `src/lib/schemas/`
5. Field names match wire format exactly
6. Nullability matches Pydantic (`| None` ↔ `.nullable().optional()`)
7. Enums match Literal values exactly
8. `src/lib/api/endpoints.ts` updated with new path(s)
9. React Query hook updated to use new schema
10. Playwright visual check passes (data renders, no console errors)
