# Forge-OH Architecture

Forge-OH is an AI coding assistant that wraps OpenHands with a production-grade
BFF (Backend For Frontend), a Next.js 16 dashboard, and a Rigpa-LMS integration.

## System Layers

```
 Browser
   │
   ├── Next.js 16 frontend (src/)
   │     ├── App Router pages  (src/app/)
   │     ├── Feature slices    (src/features/)
   │     ├── Shared components (src/components/)
   │     └── Zustand stores    (src/lib/state/)
   │
   ├── Next.js API routes (src/app/api/) — BFF proxy boundary
   │
   ├── BFF FastAPI (bff/)
   │     ├── Routers     (bff/routers/)
   │     ├── Services    (bff/services/)
   │     └── Socket.IO   (bff/main.py → app_with_sio)
   │
   └── OpenHands sandbox (never called from the browser directly)
```

## Key Constraints

- The browser never calls OpenHands directly.
- All model routing happens in `bff/services/model_router.py`. The frontend has
  no model awareness.
- Socket.IO is the primary streaming transport. The ASGI entry point is
  `bff.main:app_with_sio` — never `bff.main:app`.
- Authentication tokens are currently in-memory (`bff/auth_state.py`). This
  limits deployment to a single Uvicorn worker. Migrate to Redis before scaling.
