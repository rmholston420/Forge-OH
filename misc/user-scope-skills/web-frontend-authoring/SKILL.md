---
name: web-frontend-authoring
description: Hazards and idioms for authoring TypeScript/React/Next.js frontend code. Use when creating a new page or component, adding a react-query hook, defining a zod schema for an API response, working across the RSC/client boundary, or debugging hydration errors. Covers Next.js 14/15/16 App Router, react-query v5 patterns, zod schema hygiene, and the client/server component split.
license: MIT
triggers:
  - Next.js
  - React
  - react-query
  - TanStack Query
  - useQuery
  - zod
  - App Router
  - RSC
  - server component
  - client component
  - hydration
  - "use client"
---

# Web Frontend Authoring

Applies to any TypeScript + React + Next.js App Router codebase using @tanstack/react-query and zod for schema validation.

## The RSC / Client Boundary — Where Things Break

Next.js App Router splits components into two categories:

- **Server components (RSC)** — default. Run only on the server. Can `await` directly. Cannot use `useState`, `useEffect`, `useQuery`, event handlers, or the `window` object.
- **Client components** — anything with `'use client'` at the top. Can use hooks, event handlers, and browser APIs.

Rules:

- Put `'use client'` at the top of files that use react-query hooks, event handlers, or browser APIs.
- A server component can import and render a client component. A client component can also render a server component only if it was passed as a prop (`children`).
- Never `await` a promise directly in a client component — use `useQuery`, `useSuspenseQuery`, or move the fetch to a server component.

If you get `You're importing a component that needs useState. This React hook only works in a client component`, add `'use client'` at the top of the file with the hook.

## Hydration Mismatches

Hydration errors happen when server-rendered HTML differs from what the client renders on first pass. Common causes:

1. **Time-based rendering** — `new Date().toLocaleString()` differs between server and client. Fix: render on client only via `useEffect` + state.
2. **`window` access during render** — server has no `window`. Fix: `typeof window !== 'undefined'` guard OR `useEffect`.
3. **Locale-dependent formatting** — number/date formatting without an explicit locale.
4. **Nondeterministic order** — `Object.keys()` over a Map, `Set` iteration, `Math.random()`.

If the error names a specific element, that element or one of its ancestors is the mismatch source — not the whole tree.

## react-query v5 Patterns

### Query key hygiene

Keys are how react-query invalidates and dedupes. Structure them consistently:

```typescript
// ✅ Good — hierarchical, invalidatable
useQuery({ queryKey: ['runs'], queryFn: fetchRuns });
useQuery({ queryKey: ['runs', runId], queryFn: () => fetchRun(runId) });
useQuery({ queryKey: ['runs', runId, 'events'], queryFn: () => fetchEvents(runId) });

// ❌ Bad — flat, can't invalidate a group
useQuery({ queryKey: ['run-list'], ... });
useQuery({ queryKey: ['run-detail-' + runId], ... });
```

Invalidate a whole subtree with `qc.invalidateQueries({ queryKey: ['runs'] })`.

### Never `useQuery` in a loop or condition

```typescript
// ❌ Hook order violation
items.map(item => useQuery({ queryKey: ['item', item.id], ... }));

// ✅ Batch — one query for the list
useQuery({ queryKey: ['items'], queryFn: fetchAllItems });

// ✅ Or useQueries for a fixed set
useQueries({ queries: items.map(item => ({ queryKey: [...], queryFn: ... })) });
```

### Mutations invalidate on success

```typescript
const qc = useQueryClient();
useMutation({
  mutationFn: createRun,
  onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
});
```

## Zod Schema Hygiene

Schemas MUST match the backend response shape exactly. When they drift, you get silent runtime errors (with `.safeParse`) or crashes (with `.parse`) that look like backend bugs.

Rules:

- Every API response has a zod schema in `src/lib/schemas/*.ts` OR `src/features/*/schemas.ts`.
- The response schema's fields match the backend's field names *and* casing exactly.
- If the backend returns snake_case and you want camelCase in the FE, do the transform in `api.ts` — not in the component.

```typescript
// ✅ Transform at the API boundary
export async function fetchRuns(): Promise<Run[]> {
  const raw = await bffGet<{ data: unknown[] }>(ENDPOINTS.RUNS.list());
  return z.array(RunSchema).parse(raw.data);
}
```

## TypeScript Strict Mode — Common Fixes

- `noUncheckedIndexedAccess: true` means `arr[0]` is `T | undefined`. Handle it: `const first = arr[0]; if (!first) return null;`
- `strictNullChecks` catches most bugs — never disable it locally
- If a type gets weird after a library upgrade, check the library's changelog before casting

## Anti-Patterns

- ❌ `useEffect` to fetch data (use react-query instead)
- ❌ Prop-drilling react-query state through 4 levels (colocate the hook)
- ❌ `any` in TypeScript — use `unknown` and narrow
- ❌ Client-side data fetching in a server component (`await fetch()` is fine; `useQuery` is not)
- ❌ Missing `key` prop on list items (React silently re-renders wrong things)
- ❌ Inline event handlers with expensive computation — memoize
- ❌ Global CSS in a component file — use CSS modules or Tailwind
- ❌ Defining Zod schemas inside a component (recreated every render)

## Debug Checklist for a "Broken" Component

1. Is `'use client'` at the top? (if it uses hooks)
2. Does the console show a hydration error? (server ≠ client output)
3. Is the query key stable across renders? (`['x', someObject]` — the object is a new reference each render)
4. Is a Zod schema silently rejecting a response? (`.safeParse().success === false`)
5. Is the mutation's `onSuccess` firing? (breakpoint the invalidation)
