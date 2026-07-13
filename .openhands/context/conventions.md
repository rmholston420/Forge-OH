# Forge-OH Coding Conventions

## Python (BFF)

- Python 3.13+. Type hints on all public functions.
- All I/O in async FastAPI routes must be non-blocking. Use `aiosqlite` for
  SQLite, `httpx.AsyncClient` for HTTP, `asyncio.to_thread()` for any remaining
  sync calls.
- Pydantic v2 models for all request/response bodies.
- Never import from `bff.main:app` — import from `bff.main:app_with_sio`.

## TypeScript (Frontend)

- TypeScript strict mode. No `any` without an explanatory comment.
- Zod schemas in `src/lib/schemas/` are the single source of truth for all API
  shapes. Derive TypeScript types from schemas with `z.infer<>`.
- Zustand stores in `src/lib/state/` for global UI state. TanStack Query for
  server state. Never mix them.
- Socket.IO callbacks passed to `useRunStream` must be stable references
  (created with `useCallback` or stored in `useRef`). Inline arrow functions
  will cause the socket to reconnect on every render.
- Feature slices in `src/features/` are self-contained: hooks, store, types,
  and components co-located.

## Commits

Conventional Commits: `type(scope): description`
Types: feat, fix, docs, refactor, test, chore
