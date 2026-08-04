# Frontend–Backend Parity Audit

**Author:** Perplexity Computer
**Date:** 2026-08-03 21:14 EDT
**Repo state:** `main` @ `08fa3c4`
**Scope:** map every BFF resource → its frontend consumer → declare gap category. No code changes.

---

## Executive summary

- **Sidebar exposes 8 nav items.** All 8 render a page. Three of those pages are placeholder `<EmptyState/>` stubs: **Agents**, **Tools & MCP**, **Metrics**. The remaining five are real UIs of varying completeness.
- **Six BFF resources have no sidebar entry**: `notifications`, `repograph`, `trajectories`, `bash`, `git`, `secrets` (page exists but is unlinked).
- **One BFF router file is a dead stub**: `bff/routers/agents.py` — kept for future deletion; not wired.
- **"Custom skills" as a first-class concept does not exist in Forge-OH.** OpenHands calls tool-groups "skills"; Forge-OH surfaces them only as a `skills[]` field on Plugin marketplace entries (per `bff/routers/plugins.py`). The improvement-slate confirms slices D/E/F ship as in-repo modules, NOT as OpenHands `PluginDescriptor`s.

---

## Backend inventory

FastAPI routers mounted at `/api/*` (from `bff/main.py`):

| Router | Prefix | Endpoints | Wired |
|---|---|---|---|
| `agent_presets` | `/api/agent-presets` | GET, GET/{id}, POST, PATCH/{id}, DELETE/{id}, POST/{id}/duplicate, POST/{id}/set-default | ✅ |
| `agents` | — | — (empty stub) | ❌ intentionally not wired |
| `bash` | `/api/runs/{run_id}/bash` | POST, POST/execute, GET/events, DELETE/events, GET/stream | ✅ |
| `git` | `/api/runs/{run_id}/git` | GET/changes, GET/diff | ✅ |
| `gpu` | `/api/gpu` | GET, GET/history | ✅ |
| `mcp` | `/api/mcp` | GET, POST, DELETE/{id}, POST/{id}/toggle, POST/{id}/ping | ✅ |
| `metrics` | `/api/metrics` | GET, GET/summary, GET/daily, GET/models, GET/workspaces, GET/runs/{id}, GET/workspaces/{id}, GET/cost | ✅ |
| `notifications` | `/api/notifications` | GET, POST/{id}/read, POST/read-all, DELETE/{id} | ✅ |
| `observability` | `/api/observability` | GET/traces, GET/runs/{id}/traces, GET/traces/{id}, GET/traces/{id}/spans | ✅ |
| `plugins` | `/api/plugins` | GET, GET/marketplace, POST, POST/install, DELETE/{id}, POST/{id}/enable, POST/{id}/disable, POST/{id}/ping | ✅ |
| `repograph` | `/api/repograph` | GET/*, POST/* (7 endpoints) | ✅ |
| `runs` | `/api/runs` | 20 endpoints (list, create, detail, events, plan, metrics, files, artifacts, commands, browser, traces, pause, resume, stop, approve, reject, fork, compare) | ✅ |
| `secrets` | `/api/secrets` | GET, POST, PUT/{id}/rotate, DELETE/{id} + conv-secrets side router | ✅ |
| `settings` | `/api/settings` | GET, PATCH, POST/reset, GET/model-routing | ✅ |
| `trajectories` | `/api/trajectories` | GET, GET/{id}, POST/search, POST/drain | ✅ |
| `workspaces` | `/api/workspaces` | GET, GET/{id}, POST, PATCH/{id}, DELETE/{id}, POST/{id}/test | ✅ |

Total: **16 router files, 15 wired, ~95 endpoints.**

---

## Frontend inventory

Next.js pages under `src/app/(dashboard)/`:

| Page | Lines | Consumes BFF | Real UI? |
|---|---|---|---|
| `runs/page.tsx` | 153 | runs, agent-presets | ✅ real |
| `runs/[runId]/page.tsx` | 324 | runs, events, plan, metrics, trace | ✅ real |
| `runs/[runId]/artifacts/page.tsx` | 96 | runs/{id}/artifacts | ✅ real |
| `runs/[runId]/files/page.tsx` | 7 | (empty shell) | ❌ stub |
| `runs/[runId]/terminal/page.tsx` | 7 | (empty shell) | ❌ stub |
| `runs/compare/page.tsx` | 157 | runs/compare | ✅ real |
| `agents/page.tsx` | 6 | — | ❌ EmptyState stub |
| `workspaces/page.tsx` | 66 | workspaces | ✅ real |
| `tools-mcp/page.tsx` | 6 | — | ❌ EmptyState stub |
| `plugins/page.tsx` | 105 | plugins | ✅ real (feature-flagged) |
| `metrics/page.tsx` | 6 | — | ❌ EmptyState stub |
| `observability/page.tsx` | 188 | observability | ✅ real |
| `settings/page.tsx` | 273 | settings, model-routing, agent-presets | ✅ real |
| `settings/secrets/page.tsx` | 6 | — | ❌ EmptyState stub |
| `secrets/page.tsx` | 99 | secrets | ✅ real (feature-flagged, **unlinked**) |

Total: **16 pages, 9 real, 6 stubs, 1 empty root.**

Feature modules present in `src/features/` but with no matching page or sidebar link:
- `notifications` — hooks + api present, no UI consumer
- `trajectory-memory` — hooks + api present, no UI consumer
- `repograph` — hooks + api present; consumed only inside RepoGraphPanel component, no top-level page
- `agent-presets` — consumed inside `settings/page.tsx` and `runs/page.tsx`; no dedicated management page

---

## Sidebar (source of truth: `src/components/navigation/Sidebar.tsx`)

```
Runs           → /runs           ✅ real
Agents         → /agents         ❌ stub (EmptyState)
Workspaces     → /workspaces     ✅ real
Tools & MCP    → /tools-mcp      ❌ stub (EmptyState)
Plugins        → /plugins        ✅ real
Metrics        → /metrics        ❌ stub (EmptyState)
Observability  → /observability  ✅ real
Settings       → /settings       ✅ real
```

CommandPalette exposes: `goto-runs`, `goto-workspaces`, `goto-settings` (three entries only).

---

## Gap categorization

### Category A — Sidebar link present, page is a stub

These are visible in the nav but do nothing when clicked. **Highest user-visible pain.**

| Nav entry | Backend | Fix scope |
|---|---|---|
| **Agents** | `/api/agent-presets/*` (7 endpoints, fully implemented) | Frontend-only: build a real Agent Presets page. Data layer (`src/features/agent-presets/`) already exists. |
| **Tools & MCP** | `/api/mcp/*` (5 endpoints, fully implemented) | Frontend-only: build a real MCP server management page. Data layer (`src/features/mcp/`) already exists. |
| **Metrics** | `/api/metrics/*` (8 endpoints, fully implemented) | Frontend-only: build a real Metrics dashboard. Data layer (`src/features/metrics/`) already exists. |

### Category B — Backend + data-layer present, no nav link at all

These features work end-to-end from the API but a user cannot reach them.

| Feature | Backend | Frontend data layer | Fix scope |
|---|---|---|---|
| **Notifications** | `/api/notifications/*` (4 endpoints) | `src/features/notifications/` (hooks + api) | Add nav entry + build page, OR expose as a Topbar bell dropdown (recommended per common UX pattern). |
| **Secrets** | `/api/secrets/*` (5 endpoints) | `src/features/secrets/` + real 99-line page at `/secrets` | Add nav entry pointing at existing `/secrets` page. Also remove the dead 6-line `settings/secrets/page.tsx` stub. |
| **Trajectories** | `/api/trajectories/*` (4 endpoints) | `src/features/trajectory-memory/` (hooks + api) | Add nav entry + build page. May want to be a Settings sub-tab instead of top-level. |
| **RepoGraph** | `/api/repograph/*` (7 endpoints) | `src/features/repograph/` + `RepoGraphPanel.tsx` component | Currently only reachable via embed inside a Run Detail tab. If a top-level explorer is desired, add nav + page. |

### Category C — Category-B backend that only makes sense contextually

These probably should NOT get their own top-level nav; they are per-run concerns.

| Feature | Backend | Current wiring | Notes |
|---|---|---|---|
| **Bash / Terminal** | `/api/runs/{id}/bash/*` (5 endpoints) | `runs/[runId]/terminal/page.tsx` is a 7-line stub, but the components in `src/features/terminal/` are real | Fix scope: replace the 7-line stub with the real terminal shell already built. |
| **Git changes/diff** | `/api/runs/{id}/git/*` (2 endpoints) | `runs/[runId]/tabs/FilesTab.tsx` exists as tab; `runs/[runId]/files/page.tsx` is a 7-line stub | Same: replace the stub route with a real page or drop the route entirely and keep the tab. |
| **Run traces** | `/api/runs/{id}/traces` + `/api/observability/*` | Observability page exists (188 lines) | Already wired. No gap. |

### Category D — Router files that shouldn't exist

- **`bff/routers/agents.py`** — documented as "DEPRECATED — intentionally empty." Delete per the `TODO(foh-phase2)` in the file.

### Category E — Missing per-Slice concepts

Per the Definitive Build Plan §Phase 3–5, the following are named but not yet built:
- **Slice 4A Browser Session View** — no frontend page, `runs/{id}/browser` endpoint exists.
- **Slice 4C Trace Explorer** — a top-level trace explorer (deeper than the Observability dashboard) is planned; not present.
- **Slice 5A Approval / Intervention** — backend `POST /runs/{id}/approve|reject|pause|resume` exists; no dedicated Approvals inbox page in the frontend.
- **Slice 5B Replay** — `POST /runs/{id}/fork` and Compare page exist; a dedicated Replay UI is not present.

---

## Gap-to-slice mapping (proposed F.20 series)

Each gap becomes one build slice. Each slice has its own Definition of Done and stop condition. See `docs/decisions/2026-08-03-frontend-parity-plan.md` for the sequenced plan and `docs/adr/010-frontend-parity-scope.md` for the load-bearing scoping decision.

| Slice | Category | Deliverable | Estimated effort |
|---|---|---|---|
| F.20 | D | Delete `bff/routers/agents.py` stub, remove `settings/secrets/page.tsx` stub | trivial (~15 min) |
| F.21 | A | Build real Agents (agent-presets) page | ~1 slice |
| F.22 | A | Build real Tools & MCP page | ~1 slice |
| F.23 | A | Build real Metrics dashboard page | ~1 slice |
| F.24 | B | Wire Notifications (Topbar bell + optional page) | ~1 slice |
| F.25 | B | Link existing Secrets page into Sidebar; clean up stub route | ~0.5 slice |
| F.26 | B | Trajectories page (or Settings sub-tab, decide in the slice) | ~1 slice |
| F.27 | C | Replace `runs/[runId]/terminal` stub with real terminal | ~0.5 slice |
| F.28 | C | Replace `runs/[runId]/files` stub with real file view (or remove route) | ~0.5 slice |
| F.29 | E | Browser Session View (Slice 4A) | ~1 slice |
| F.30 | E | Trace Explorer top-level page (Slice 4C) | ~1 slice |
| F.31 | E | Approvals inbox page (Slice 5A support UI) | ~1 slice |

F.20–F.28 close the frontend-backend parity gap. F.29–F.31 are net-new Definitive-Plan slices, not parity work.

---

## Non-goals of this audit

- Does not decide whether to build any of these slices. That is per-slice sequencing.
- Does not touch backend code — no route additions or deletions here.
- Does not evaluate frontend code quality beyond "is the page a stub or real."
- Does not audit design-system conformance.
- Does not analyze cross-repo (Kosmos/Tektos) reuse — see the separate Kosmos plugin analysis document.
