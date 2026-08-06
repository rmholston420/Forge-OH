---
name: forge-oh-repo-navigation
description: How to find things in the Forge-OH repo — where routers live, where services live, where FE features live, where docs live, and which existing patterns to copy. Use whenever starting a new feature and asking "where does this go?", when investigating a bug and asking "where is this defined?", or when looking for a similar existing implementation to base new code on. Enforces the "copy an existing pattern, don't invent" rule.
license: MIT
triggers:
  - "bff/routers"
  - "bff/services"
  - "src/features"
  - "src/lib/schemas"
  - "src/lib/api"
  - "src/app"
  - where does
  - where is
  - similar to
  - existing pattern
  - "scripts/forge-"
  - "docs/reconciliation-plan"
  - "adrs/"
  - BUILD_LOG
  - DEBUG_LOG
  - SESSION_HANDOFF
---

# Forge-OH Repo Navigation

Applies to any "where does this go?" question in the Forge-OH repo. Verified against the actual layout at `~/dev/forge-oh` on Colossus.

## Repo Layout (top level)

```
~/dev/forge-oh/
├── AGENTS.md              ← agent-facing project instructions
├── BUILD_LOG.md           ← append-only build log
├── DEBUG_LOG.md           ← append-only debug log — SEARCH FIRST
├── SESSION_HANDOFF.md     ← overwritten each session
├── PORTING_LEDGER.md      ← every OSS vendor entry
├── KNOWN_ISSUES.md
├── Caddyfile
├── next.config.ts
├── package.json
├── pnpm-lock.yaml
├── requirements.txt / pyproject.toml
├── playwright.config.ts   ← Playwright config (used from src/)
├── .agents/skills/        ← project-scope skills live here
├── .oh-venv/              ← Python venv
├── .next/                 ← Next.js build output
├── adrs/                  ← Architecture Decision Records
├── docs/                  ← planning + reference docs
├── bff/                   ← FastAPI backend-for-frontend
├── src/                   ← Next.js app
├── scripts/               ← ops scripts (forge-up.sh, etc.)
├── screenshots/           ← Playwright screenshots (gitignored, force-added)
├── openhands_tools_ext/   ← custom OpenHands SDK extensions
└── tests/                 ← top-level e2e config
```

## BFF Layout (`bff/`)

```
bff/
├── main.py                ← FastAPI + Socket.IO wrapper (app_with_sio)
├── routers/               ← ONE file per resource
│   ├── agent_presets.py   ← COPY THIS as a router template
│   ├── runs.py
│   ├── skills.py
│   ├── workspaces.py
│   ├── gpu.py
│   ├── memory.py
│   └── ... (~25 files)
├── services/              ← business logic; NOT HTTP-facing
│   ├── event_normalize.py     ← agent-server event → wire shape
│   ├── event_relay.py         ← BFF ↔ Socket.IO bridge
│   ├── event_commit_ledger.py ← event persistence
│   ├── idempotency_ledger.py  ← create-request dedup
│   ├── inference_backends/    ← model routing
│   ├── model_router.py
│   ├── loop_guard.py
│   └── ... (many)
└── tests/
    ├── conftest.py
    └── test_<router>_router.py
```

**Rule:** routers handle HTTP + Pydantic validation; services hold logic. Never put business logic in a router. Never call `httpx` from a router without going through a service.

## Frontend Layout (`src/`)

```
src/
├── app/                   ← Next.js App Router pages
│   ├── layout.tsx
│   ├── runs/
│   ├── workspaces/
│   ├── agent-presets/
│   └── ... (one dir per top-level route)
├── features/              ← feature modules (colocated hooks + components)
│   ├── runs/
│   ├── agent-presets/
│   └── ...
├── components/            ← shared UI components (Buttons, Modals, etc.)
├── lib/
│   ├── api/
│   │   ├── endpoints.ts   ← FE endpoint registry (see bff-fe-contract-sync)
│   │   └── http/          ← fetchJson wrapper
│   ├── schemas/           ← Zod schemas mirroring BFF Pydantic
│   │   ├── agent-preset.ts
│   │   ├── run.ts
│   │   ├── skill.ts
│   │   └── ... (many)
│   ├── streaming/         ← Socket.IO hooks
│   ├── state/             ← Zustand / React Query stores
│   └── ...
├── tests/
│   └── e2e/               ← Playwright specs
└── playwright.config.ts
```

**Rule:** pages in `app/` are thin — routing + layout + feature-module composition. Feature logic lives in `src/features/<name>/`.

## Docs Layout (`docs/`)

```
docs/
├── reconciliation-plan-v1.md            ← CANONICAL plan (supersedes v4)
├── reconciliation-plan-v1-stage-1.md    ← per-stage detail
├── reconciliation-plan-v1-stage-2.md
├── ... (through stage 7)
├── planning/                            ← ad-hoc plan documents
└── ...
```

**Rule:** `reconciliation-plan-v1.md` is the source of truth. `Forge-OH-Action-Plan-v4.md` is superseded (see AGENTS.md § Canonical Planning Documents).

## ADRs (`adrs/`)

```
adrs/
├── README.md              ← ADR index
├── 001-use-ollama-first.md
├── ... (many)
```

New architectural decision → new ADR file, follow `kosmos-adr-authoring` (or the local template if it differs).

## Scripts (`scripts/`)

Four canonical scripts — use them, don't hand-roll:

- `forge-up.sh` — start dev stack (agent-server + BFF + Next dev)
- `forge-down.sh` — stop dev stack cleanly
- `forge-restart.sh` — down + up (`--bff-only`, `--status` supported)
- `forge-status.sh` — health snapshot
- `forge-doctor.sh` — full diagnostic

See `forge-oh-colossus-ops` for detail. **Never write ad-hoc `nohup uvicorn` chains — extend a script instead.**

## When Adding a New Feature — Where to Put What

| Layer | Location | Example |
|---|---|---|
| BFF route | `bff/routers/<name>.py` | `bff/routers/skills.py` |
| BFF business logic | `bff/services/<name>.py` | `bff/services/event_normalize.py` |
| BFF test | `bff/tests/test_<name>_router.py` | `bff/tests/test_skills_router.py` |
| FE schema | `src/lib/schemas/<name>.ts` | `src/lib/schemas/skill.ts` |
| FE endpoint constant | `src/lib/api/endpoints.ts` (add block) | `ENDPOINTS.SKILLS` |
| FE page | `src/app/<name>/page.tsx` | `src/app/skills/page.tsx` |
| FE feature module | `src/features/<name>/` | `src/features/skills/api.ts` |
| FE Playwright spec | `src/tests/e2e/<name>.spec.ts` | `src/tests/e2e/skills-page.spec.ts` |
| Sidebar nav link | `src/components/Sidebar.tsx` (add entry) | — |
| ADR (if architectural) | `adrs/NNN-<title>.md` | `adrs/025-skills-page.md` |

## Existing Patterns to Copy

When adding X, start by reading Y:

| Adding… | Copy from… |
|---|---|
| A new BFF router | `bff/routers/agent_presets.py` |
| A new proxy to agent-server | `bff/routers/mcp.py` or `plugins.py` |
| A new Zod schema | `src/lib/schemas/agent-preset.ts` |
| A new list page | `src/app/agent-presets/page.tsx` |
| A new detail page | `src/app/runs/[id]/page.tsx` |
| A new event type | `bff/services/event_normalize.py` |
| A new Socket.IO consumer | `src/lib/streaming/useRunEvents.ts` |
| A new Playwright spec | any recent spec in `src/tests/e2e/` |
| A new ADR | any ratified ADR in `adrs/` |

**Rule: copy, don't invent.** New code that follows a different pattern than the surrounding code creates review load and drift.

## Finding Things

### "Where is this endpoint implemented?"

```bash
grep -rn 'prefix="/<partial>"' bff/routers/
```

### "Where is this Zod schema used?"

```bash
grep -rn "<SchemaName>" src/
```

### "Which router calls the agent-server for X?"

```bash
grep -rn "AGENT_SERVER_URL\|8090" bff/routers/ bff/services/
```

### "Where does this event type come from?"

```bash
grep -n "\"<event_type>\"" bff/services/event_normalize.py
# then grep for the SDK class name in agent-server source
```

### "What ADR governs this decision?"

```bash
grep -rn "<topic>" adrs/README.md
# then read the referenced ADR
```

### "Is there a build-log entry about this?"

```bash
grep -in "<topic>" BUILD_LOG.md DEBUG_LOG.md
```

## AGENTS.md Precedence

`AGENTS.md` at repo root defines the canonical workflow rules for AI agents. Read it once at session start. Anything in AGENTS.md wins over any assumption from a skill.

Key items from AGENTS.md:
- Canonical planning doc is `docs/reconciliation-plan-v1.md`
- `Forge-OH-Action-Plan-v4.md` is superseded
- Stage stop conditions in `reconciliation-plan-v1.md` are stricter than DoD when they conflict

## Common Navigation Mistakes

### Editing `Forge-OH-Action-Plan-v4.md`

It's superseded. Edit `docs/reconciliation-plan-v1.md` or the per-stage companion.

### Adding a new resource to an existing router

Don't. One resource per router. If `skills.py` doesn't exist, create it — don't tack skills endpoints into `plugins.py`.

### Putting a Zod schema in the feature folder

Zod schemas live in `src/lib/schemas/`, not in feature folders. This makes them reusable and discoverable.

### Adding a component directly under `src/components/` for feature-specific UI

Only truly shared components (Button, Modal, Toast) live in `src/components/`. Feature-specific components go under `src/features/<name>/components/`.

### Editing `.openhands/skills/` when authoring a new skill

Use `.agents/skills/`. The SDK prefers this path; `.openhands/skills/` is legacy.

## Anti-Patterns

- ❌ Not searching the repo for an existing similar pattern before writing new code
- ❌ Editing superseded docs (Forge-OH-Action-Plan-v4.md)
- ❌ Multiple resources in one router file
- ❌ Business logic in routers
- ❌ Feature logic in `src/app/*/page.tsx` (should be thin routing shell)
- ❌ New Zod schemas under `src/features/` instead of `src/lib/schemas/`
- ❌ Skipping the AGENTS.md read at session start
- ❌ Skipping DEBUG_LOG.md search before diagnosing a bug (mandatory per project instructions)
- ❌ Hand-rolling ops commands when a `scripts/forge-*.sh` covers it

## Checklist Before Starting a Feature

1. Read AGENTS.md (once per session)
2. Read `docs/reconciliation-plan-v1.md` + relevant stage companion — the scope is defined there
3. Search the repo for the closest existing pattern
4. Identify the "copy from" file for each layer (router, schema, page, spec)
5. Note dependencies: does this need a new event type? A new agent-server proxy? A new ADR?
6. Draft the file list to touch — matches the layer table above
7. Check whether an ADR is needed (see `kosmos-adr-authoring`)
