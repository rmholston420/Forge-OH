# Forge-OH

> A standalone AI coding assistant UI powered by OpenHands, built to become the **Forge plugin** for Rigpa-LMS.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 15 (App Router) |
| Styling | CSS Modules + Nexus design tokens |
| State | Zustand (UI) + TanStack Query (server) |
| Forms | React Hook Form + Zod |
| Streaming | Socket.IO client |
| Code editing | Monaco Editor (diff viewer) |
| Terminal | xterm.js + FitAddon |
| BFF | FastAPI (Python) |
| Testing | Vitest + React Testing Library + Playwright |
| Mocks | MSW 2 |

---

## Phase Status

| Phase | Scope | Status |
|---|---|---|
| 0 | App shell, BFF scaffold, MSW mocks, nav | ✅ Complete |
| 1 | Runs home, run detail, streaming, plan rail, approval banner | ✅ Complete |
| 2 | Monaco diff viewer, xterm terminal, artifact viewer | ✅ Complete |
| 3 | Workspaces, MCP servers, plugin registry, secrets vault | ✅ Complete |
| 4 | Browser viewer, observability dashboard, trace explorer | ✅ Complete |
| 5 | Settings, notification centre, onboarding tour | ✅ Complete |
| 6 | Auth (NextAuth), RBAC, Rigpa-LMS plugin bridge | 🕒 Planned |

---

## Feature Inventory

### Runs
- Runs list with live 5s polling, search, status + workspace filters
- New Run composer (React Hook Form + Zod, agent preset + workspace dropdowns)
- Run detail with Socket.IO streaming event timeline (9 event types)
- Tabbed run detail: Overview • Files • Terminal • Browser • Metrics • Trace • Artifacts • Security
- Plan Rail: 6 node states, recursive children, live progress counter
- Approval Banner: full-width amber, `aria-live="assertive"`, approve/reject
- Run controls: pause, resume, stop, fork (sticky header)

### Files & Code
- Monaco diff viewer with forge-dark/light themes (Nexus palette)
- Split/unified toggle, binary file fallback
- File list sidebar with A/M/D/R status badges and per-file line counts

### Terminal
- xterm.js with custom ANSI 16-color Nexus themes (dark + light)
- FitAddon responsive resize, command history replay, incremental append

### Browser
- Frame scrubber, zoom, play/pause, URL bar display

### Observability
- MetricKPI tiles with trend indicators, tabular-nums
- Trace explorer: SpanRow tree with depth indentation, duration bars, status badges

### Artifacts
- 8 artifact types, type-filter chips, image/screenshot thumbnails
- ArtifactPreviewModal: lightbox, iframe for reports, Escape + backdrop dismiss

### Workspaces
- Card grid (local/docker/remote-api), health badges (text+icon, a11y safe)
- WorkspaceDetailsDrawer: file upload zone, reset confirm dialog

### Tools & MCP
- MCP server cards: status chip (text+icon), tool count, ping latency, enable/disable toggle
- Plugin registry: version badge, configSchema-driven config drawer

### Secrets
- Always-masked values (no reveal button), scope + provider badges
- SHA-256 hash stored server-side; raw value never returned from BFF

### Settings
- Appearance: theme (system/light/dark), accent color (6 swatches), font size
- Model & Agent: default model, agent preset, max concurrent runs stepper, auto-approve toggle
- Keyboard shortcuts: click-to-capture rebind, conflict detection
- Unsaved-changes guard (`beforeunload`), optimistic updates with rollback

### Notifications
- Slide-in panel from topbar bell, unread count badge (capped 99+)
- 5 notification types with icons (never color-only)
- Filter tabs: All / Unread / Run events
- Mark read, mark all read, dismiss; Escape keyboard trap

### Onboarding
- 7-step guided tour with SVG spotlight cutout over target elements
- ResizeObserver re-positions spotlight on layout change
- Keyboard nav: ArrowRight/Left/Escape
- Auto-starts for first-time users; in-memory done flag (sandbox safe)

---

## Development

```bash
# Frontend
npm install
npm run dev

# BFF
cd bff
pip install -r requirements.txt
uvicorn main:app --reload

# Tests
npm run test        # Vitest unit tests
npm run test:e2e    # Playwright
```

---

## Next: Phase 6

- **Auth**: NextAuth.js with credential + OAuth providers
- **RBAC**: role-based access control (admin / developer / viewer)
- **Rigpa-LMS plugin bridge**: deep integration between Forge-OH and Rigpa-LMS course engine
- **Real OpenHands runtime**: replace MSW mocks with live OpenHands API
