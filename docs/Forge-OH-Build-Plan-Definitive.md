# Forge-OH: Definitive Vertically-Sliced Build Plan
### Execution Blueprint for Perplexity Computer and Claude Code

***

## Executive Summary

Forge-OH is a browser-based, workspace-centered agent operations console built on the OpenHands SDK. It is **not** a generic AI chat interface — it is a supervision-first control plane for autonomous software engineering agents that eventually embeds into Rigpa-LMS as a pedagogical coding copilot. The product revolves around five first-class objects: **Run, Agent, Workspace, Tool, and Artifact**. Every design and implementation decision must trace back to those objects .

The build is organized as **18 vertical slices across 6 phases**, each independently demoable, testable, and shippable. All traffic flows through the BFF — the frontend never talks directly to OpenHands. The BFF is the policy injection point for course context, loop-guard enforcement, episodic memory recall, and delegation contract templates .

**Primary model routing**: Ollama (local, air-gapped first), with vLLM as the backup, and optional cloud models for complex tasks. The recommended primary local model is **Devstral Small 24B** for agentic workflows and **Qwen3 14B** for fast everyday scripting with headroom on the RTX 5070 with 16 GB VRAM .

***

## Pinned Stack Versions (July 2026)

These are the exact, verified, compatibility-checked versions to use. Pin them in `package.json` and `requirements.txt` from Day 1.

### Frontend `package.json`

```json
{
  "dependencies": {
    "next": "16.2.10",
    "zustand": "^5.0.14",
    "@tanstack/react-query": "^5.99.1",
    "@tanstack/react-query-devtools": "^5.99.1",
    "socket.io-client": "^4.8.3",
    "monaco-editor": "^0.55.1",
    "@xterm/xterm": "^5.5.0",
    "recharts": "^3.9.2",
    "zod": "^4.3.0"
  },
  "devDependencies": {
    "typescript": "^6.0.2",
    "vitest": "^4.1.10",
    "@playwright/test": "^1.61.0",
    "storybook": "^10.4.6"
  }
}
```

**Critical notes** :
- Do **not** pin `react` or `react-dom` separately — Next.js 16 ships React 19 internally
- TypeScript 6.0 enables `strict: true` by default — run `tsc --noEmit` before CI gates
- `@xterm/xterm` (with `@xterm/` scope) is the correct import, not legacy `xterm`
- TypeScript 7.0 (July 8, 2026) is too new — stay on TS 6.0.x for now
- Socket.IO must be `^4.8.3` or later due to CVE-2026-33151 fix

### BFF `requirements.txt`

```
fastapi==0.136.2
pydantic>=2.12.5,<3.0
uvicorn[standard]>=0.34
python-socketio>=5.11
openhands==cloud-1.46.0
ollama>=0.31.2
vllm>=0.25.0
```

> ⚠️ **Known issue — `openhands` pip version string**: `cloud-1.46.0` is not a valid PyPI version identifier (hyphens are not permitted). Until a proper PyPI release exists, install via a direct GitHub release URL or a private index. Do not rely on `pip install openhands==cloud-1.46.0` succeeding in a clean environment.

**Runtime targets** :
- Python: `3.13.x`
- Node.js: `24.18.0` LTS
- OpenHands: `cloud-1.46.0` (released July 10, 2026)
- Ollama: `v0.31.2` (released July 7, 2026)
- vLLM: `v0.25.0` (released July 11, 2026)

***

## Model Routing Strategy

The Forge BFF implements a tiered routing policy — no model selection touches the frontend .

| Tier | Model | Backend | VRAM | Use Case |
|------|-------|---------|------|----------|
| **Primary** | Devstral Small 24B (Q4_K_M) | Ollama local | ~16 GB | Agentic workflows, multi-file refactoring, debugging loops |
| **Fast** | Qwen3 14B (Q4_K_M) | Ollama local | ~9 GB | Fast scripting, quick summaries, context headroom |
| **Backup** | vLLM (any model) | Local vLLM server | configurable | When Ollama is unavailable or context exceeds 32K |
| **IDE autocomplete** | Codestral 22B (Q4_K_M) | Ollama local | ~14 GB | FIM-optimized autocomplete via Continue.dev |

**KV cache note**: Set `PARAMETER num_ctx 32768` in Ollama Modelfiles. With Devstral 24B loaded (~16 GB), KV cache headroom is near zero — when long sessions are expected, route to Qwen3 14B (9 GB weights leave ~7 GB for 32K context) .

**Never go below Q4_K_M quantization** — Q3_K_S introduces syntax errors in generated code .

***

## Architecture

Forge-OH uses a strict four-layer architecture. Each layer has a single responsibility and clean contract boundaries .

```
┌─────────────────────────────────────────────────────┐
│  Rigpa-LMS Plugin Shell (Phase 5C)                   │
│  Auth · Permissions · Course Context · LMS Exchange  │
│  TypeScript · React · LMS Plugin API                 │
├─────────────────────────────────────────────────────┤
│  Forge-OH Frontend                                   │
│  Next.js 16 App Router · Zustand 5 · TanStack Q 5   │
│  Socket.IO 4.8 · Monaco 0.55 · xterm 5.5            │
├─────────────────────────────────────────────────────┤
│  Forge BFF / Orchestration Service                   │
│  FastAPI 0.136 · Pydantic 2.12 · Python 3.13        │
│  context_loader · loop_guard · episodic_memory       │
│  conflict_checker · audit_log                        │
├─────────────────────────────────────────────────────┤
│  OpenHands Agent Server (cloud-1.46.0)               │
│  Ollama v0.31.2 (primary) · vLLM v0.25.0 (backup)   │
│  Docker workspaces · REST/WS APIs                    │
└─────────────────────────────────────────────────────┘
```

**The single most important architectural rule**: The frontend never talks directly to OpenHands. All traffic flows through the BFF .

### Self-Building Safety Model

Because Forge-OH will eventually be built by Forge-OH, the system enforces a strict separation :

- **Control plane** — the running Forge-OH instance the operator uses
- **Target plane** — the checked-out branch or Docker worktree the agent may modify

Self-changes gate: plan approval → code generation in isolated target → human diff review → automated checks pass → merge/promote.

| Risk Class | Examples | Policy |
|-----------|---------|--------|
| Low-risk | UI copy, styles, non-critical components | Normal review |
| Medium-risk | API handlers, state models, session logic | Explicit approval required |
| High-risk | App bootstrap, auth, DB migrations, release scripts | Elevated approval + extra checks |

***

## BFF Engineering Improvements

These five modules must be implemented in the BFF **before Phase 1 feature work begins** .

### 1. Loop Guard (`bff/services/loop_guard.py`)

> ✅ **Corrected reference implementation** (July 13, 2026 audit): The original spec had an off-by-one bug — it counted history *before* appending the new fingerprint, causing loops to be detected on the 4th occurrence instead of the 3rd. The correct implementation appends first, then counts.

```python
import hashlib
from collections import deque
from dataclasses import dataclass
from typing import Deque

@dataclass
class ActionFingerprint:
    operation_class: str   # "edit_file", "run_test", "rewrite_func"
    target: str            # normalized file path or function name
    approach: str          # "syntax", "logic", "structural"

class LoopGuard:
    def __init__(self, window: int = 5, threshold: int = 3):
        self.history: Deque[str] = deque(maxlen=window)
        self.threshold = threshold

    def fingerprint(self, fp: ActionFingerprint) -> str:
        key = f"{fp.operation_class}:{fp.target}:{fp.approach}"
        return hashlib.md5(key.encode()).hexdigest()

    def is_looping(self, fp: ActionFingerprint) -> bool:
        h = self.fingerprint(fp)
        # IMPORTANT: append BEFORE counting so the threshold is evaluated
        # against the full inclusive history (triggers on 3rd hit, not 4th).
        self.history.append(h)
        count = sum(1 for x in self.history if x == h)
        return count >= self.threshold

    def suggest_escalation(self, fp: ActionFingerprint) -> str:
        escalation_map = {
            "syntax": "structural",
            "structural": "rewrite",
            "rewrite": "delegate_to_human",
        }
        return escalation_map.get(fp.approach, "delegate_to_human")

    def reset(self) -> None:
        """Clear loop detection history (e.g., after a successful escalation)."""
        self.history.clear()
```

### 2. Product Context Loader (`bff/services/context_loader.py`)

Reads `.openhands/context/` ADR directory and injects relevant documents into the planning phase via keyword-overlap scoring. Prevents the 46% → 95% compliance gap identified in agentic coding research .

```
.openhands/
└── context/
    ├── architecture.md
    ├── conventions.md
    ├── decisions/
    │   ├── 001-use-ollama-first.md
    │   └── 002-no-direct-openhands.md
    └── personas/
        └── target-user.md
```

> ⚠️ **Gap**: The `.openhands/` directory and all five context files must be created at repo root. Without them, `context_loader.py` silently injects nothing — a correctness failure that will not crash the BFF but will degrade agent planning quality.

### 3. Episodic Memory (`bff/services/episodic_memory.py`)

SQLite-backed cross-session memory store that persists key facts, past decisions, and failed approaches across sessions. Queries this store at the start of each planning step to handle multi-day, long-horizon tasks without context fragmentation .

### 4. Conflict Checker (`bff/services/conflict_checker.py`)

Pre-PR merge simulation to detect conflicts before opening pull requests. Addresses the documented **27.67% merge conflict rate** in agentic PRs. Attempts auto-resolution for simple cases and flags complex conflicts in PR descriptions .

### 5. Delegation Contract Templates

Standardized output contract format for every agent task: what was changed, what was left incomplete, known limitations, and residual risks. Injected automatically by the BFF before dispatching to OpenHands .

***

## Design System (Implementation-Ready)

The agent must use these exact token values and must **never invent new token names** .

### Color Tokens (`src/styles/tokens.css`)

```css
:root {
  /* Background */
  --color-bg-canvas: #0F1115;
  --color-bg-app: #12151B;
  --color-bg-sidebar: #131722;
  --color-bg-topbar: #141A24;
  --color-bg-surface: #171D29;
  --color-bg-surface-alt: #1C2331;
  --color-bg-surface-elevated: #232C3E;
  --color-bg-surface-inset: #10151D;
  --color-bg-overlay: rgba(5, 8, 13, 0.72);

  /* Borders */
  --color-border-subtle: rgba(255,255,255,0.08);
  --color-border-default: rgba(255,255,255,0.12);
  --color-border-strong: rgba(255,255,255,0.18);
  --color-border-accent: rgba(77,163,255,0.44);

  /* Text */
  --color-text-primary: #F4F7FB;
  --color-text-secondary: #BAC4D6;
  --color-text-tertiary: #8893A7;
  --color-text-muted: #6E788B;
  --color-text-accent: #A9D0FF;
  --color-text-success: #9BE6BF;
  --color-text-warning: #FFD789;
  --color-text-error: #FFB0B7;

  /* Accent */
  --color-accent-primary: #4DA3FF;
  --color-accent-hover: #6CB4FF;
  --color-accent-active: #3D8DE3;
  --color-accent-soft: rgba(77,163,255,0.14);

  /* State */
  --color-state-success: #35C47C;
  --color-state-warning: #F2B84B;
  --color-state-error: #F0616B;
  --color-state-paused: #C28BFF;
  --color-state-running: #4DA3FF;

  /* Diff */
  --color-diff-added-bg: rgba(53,196,124,0.12);
  --color-diff-removed-bg: rgba(240,97,107,0.12);

  /* Terminal */
  --color-terminal-bg: #0D1219;
  --color-terminal-command: #D5E6FF;
  --color-terminal-stderr: #FF9EA6;
  --color-terminal-prompt: #7AA2F7;

  /* Typography */
  --font-ui: 'Inter', 'Satoshi', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  --font-size-body: 14px;
  --font-size-code: 12.5px;
  --font-size-meta: 12px;

  /* Spacing (4px base) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;

  /* Layout */
  --layout-topbar-height: 56px;
  --layout-tabs-height: 42px;
  --layout-sidebar-collapsed: 72px;
  --layout-sidebar-expanded: 248px;
  --layout-inspector-width: 384px;

  /* Motion */
  --motion-instant: 80ms;
  --motion-fast: 140ms;
  --motion-normal: 200ms;
  --motion-easing: cubic-bezier(0.2, 0.8, 0.2, 1);
}
```

### State Language (Universal Across All Components)

| State | Token | Color |
|-------|-------|-------|
| Idle | `--color-text-tertiary` | Grey |
| Running | `--color-state-running` | Blue |
| Streaming | `--color-accent-primary` | Blue |
| Awaiting Approval | `--color-state-warning` | Amber |
| Success | `--color-state-success` | Green |
| Failed / Blocked | `--color-state-error` | Red |
| Paused / Queued | `--color-state-paused` | Purple |
| Disconnected | `--color-state-error` | Red |

***

## Domain Model (Canonical — Never Rename)

All frontend contracts, API routes, mock fixtures, and agent context must use these exact domain object names .

| Object | Purpose |
|--------|---------|
| `Run` | One live or historical execution session (maps to OpenHands `conversation`) |
| `AgentPreset` | Reusable behavior: model, tools, policies, skills |
| `Workspace` | Execution environment: `local`, `docker`, `remote_api` |
| `ToolEvent` | Single action, observation, browser step, or file operation |
| `Artifact` | File change, patch, screenshot, report, downloadable output |
| `Integration` | MCP server, plugin, endpoint, external system |
| `TraceSpan` | OTEL record for LLM, tool, workspace, browser, network |
| `SecretRef` | Metadata only — raw values never in UI |
| `PlanNode` | One step in an agent task decomposition tree |
| `CommandExecution` | Shell command: text, cwd, exit code, duration, risk level |
| `BrowserSession` | Browser automation session: URL, step history, viewport |

***

## Repository Structure

```
forge-oh/
  src/
    app/
      (dashboard)/
        layout.tsx
        page.tsx
        runs/
          page.tsx
          [runId]/page.tsx
        agents/page.tsx
        workspaces/page.tsx
        tools-mcp/page.tsx
        plugins/page.tsx
        observability/page.tsx
        settings/
          page.tsx
          secrets/page.tsx
          providers/page.tsx
      api/
        runs/route.ts
        runs/[runId]/route.ts
        runs/[runId]/events/route.ts
        runs/[runId]/artifacts/route.ts
        runs/[runId]/commands/route.ts
        runs/[runId]/traces/route.ts
        workspaces/route.ts
        plugins/route.ts
        mcp/route.ts
        observability/route.ts
        secrets/route.ts
    components/
      core/       (button, input, tabs, badge, status-badge, table, panel,
                   empty-state, banner, modal, drawer, skeleton)
      navigation/ (sidebar, topbar, command-palette)
      domain/     (run-card, event-card, plan-node, command-block,
                   file-change-item, diff-header, workspace-card,
                   workspace-chip, mcp-server-card, plugin-card,
                   browser-session-card, secret-row, trace-span-row,
                   metric-tile)
    features/
      runs/           (api, hooks, store, schemas, mappers, selectors, fixtures)
      run-detail/     (api, hooks, store, schemas, mappers, selectors, fixtures)
      artifacts/      (api, hooks, schemas, mappers, fixtures)
      commands/       (api, hooks, schemas, mappers, fixtures)
      workspaces/     (api, hooks, schemas, mappers, fixtures)
      plugins/        (api, hooks, schemas, mappers, fixtures)
      mcp/            (api, hooks, schemas, mappers, fixtures)
      browser/        (api, hooks, schemas, mappers, fixtures)
      observability/  (api, hooks, schemas, mappers, fixtures)
      traces/         (api, hooks, schemas, mappers, fixtures)
      secrets/        (api, hooks, schemas, mappers, fixtures)
    lib/
      api/       (client, endpoints, errors, response)
      auth/      (session, permissions)
      streaming/ (socket, events, subscriptions, reconnection)
      query/     (query-client, query-keys, cache-updaters)
      schemas/   (run, event, workspace, plugin, trace, secret,
                  browser, command, artifact)
      state/     (app-store, ui-store)
      utils/     (format, date, status, download, path, assertions)
    styles/
      tokens.css
      globals.css
      theme.css
    tests/
      e2e/
      integration/
      unit/
      fixtures/
  bff/
    main.py
    routers/
      runs.py
      workspaces.py
      mcp.py
      observability.py
      secrets.py
    services/
      context_loader.py
      loop_guard.py
      episodic_memory.py
      conflict_checker.py
      model_router.py        ← Ollama-first, vLLM fallback
    openhands_client.py
  .openhands/
    context/
      architecture.md
      conventions.md
      decisions/
      personas/
```

***

## BFF Startup — Critical ASGI Entry Point

> ⚠️ **The canonical ASGI entry point is `app_with_sio`, NOT `app`.** If Uvicorn is started with `bff.main:app`, the Socket.IO server is silently bypassed and all WebSocket connections will fail.

**Correct startup command:**
```bash
uvicorn bff.main:app_with_sio --host 0.0.0.0 --port 8001 --reload
```

This must be the command used in the Dockerfile, `Makefile`, and any CI/CD scripts. Never reference `bff.main:app` as a startup target.

***

## State Management Architecture

The three-layer state separation must be maintained across all slices .

| Layer | Technology | Owns |
|-------|-----------|------|
| **Server truth** | TanStack Query | Runs list, run metadata, workspaces, plugins, MCP status, secret metadata, observability summaries, artifact indexes |
| **Stream truth** | Socket.IO → Zustand | Live `oh_event` messages, status changes, tool events, file mutations, browser actions, approval events |
| **UI truth** | Zustand | Selected tab, selected event, collapsed panes, filter text, diff mode, sort preferences, pending banners |

### Key TypeScript Interfaces

```typescript
// Core run interface
export interface RunSummary {
  id: string;
  title: string;
  status: 'idle' | 'running' | 'streaming' | 'queued' | 'paused' |
          'awaiting_approval' | 'succeeded' | 'failed' | 'blocked';
  agentPresetName: string;
  workspaceId: string;
  workspaceType: 'local' | 'docker' | 'remote_api';
  activeTool: string | null;
  updatedAt: string;
  createdAt: string;
  elapsedMs: number | null;
  estimatedCostUsd: number | null;
}

// Run detail store
export type RunDetailUIState = {
  selectedTab: 'overview' | 'files' | 'terminal' | 'browser' | 'metrics' | 'security';
  selectedEventId: string | null;
  diffMode: 'split' | 'unified';
  inspectorOpen: boolean;
  latestStreamEventId: number;
  pendingApprovalBanner: boolean;
};
```

### Streaming Architecture (Socket.IO)

> ⚠️ **Callback stability**: In `useRunStream.ts`, all callback parameters (`onEvent`, `onStatusChange`, etc.) must be wrapped in `useRef` internally before being referenced inside the `useEffect` dependency array. Passing inline arrow functions from the call site will cause the socket to disconnect and reconnect on every render — a serious performance and correctness bug.

```
1. Load run metadata + bootstrap event history over HTTP
2. Connect Socket.IO: conversation_id + latest_event_id
3. Receive oh_event messages → validate → normalize
4. Patch timeline state, run status, plan state, commands, files
5. On disconnect → reconnect with latest known event_id (avoids duplicates)
```

***

## Vertical Slice Execution Order

| Order | Phase / Slice | Deliverable |
|-------|--------------|-------------|
| 1 | **Phase 0: Foundations** | App shell, tokens, core components, MSW mocks, Storybook, E2E smoke |
| 2 | **Slice 1A: Runs Home** | Runs list, new run composer, presets/workspace selectors |
| 3 | **Slice 1B: Run Detail** | Event timeline, sticky header, Socket.IO stream, inspector |
| 4 | **Slice 1C: Plan Rail** | Plan node tree, run controls (pause/stop/fork), approval banner |
| 5 | **Slice 2A: File Diffs** | Files tab, FileChangeItem, Monaco diff viewer, patch export |
| 6 | **Slice 2B: Terminal** | xterm.js surface, CommandBlock, secret-masked output |
| 7 | **Slice 2C: Artifacts** | Artifact rail, preview cards grouped by type, downloads |
| 8 | **Slice 3A: Workspaces** | WorkspaceCard, health indicators, workspace details drawer |
| 9 | **Slice 3B: MCP + Plugins** | MCPServerCard, PluginCard, enable/disable toggles |
| 10 | **Slice 3C: Secrets** | SecretRow, always-masked values, add/edit modal |
| 11 | **Slice 4A: Browser** | BrowserSessionCard, viewport preview, navigation step history |
| 12 | **Slice 4B: Observability** | MetricTile, trend charts, slowest/most expensive runs |
| 13 | **Slice 4C: Trace Explorer** | TraceSpanRow, span tree, filters, link to EventCard |
| 14 | **Slice 5A: Approvals** | Approval banners, intervention history, approve/reject |
| 15 | **Slice 5B: Fork + Compare** | Fork action, side-by-side compare view |
| 16 | **Slice 5C: Rigpa-LMS Layer** | RigpaAgentLaunchContext, course ribbon, artifact packaging |
| 17 | **Slice 5D: AI-Agent Hardening** | README contracts, feature flags, seed data, checklist gates |
| 18 | **Slice 5E: Model Router** | Ollama-first, vLLM fallback, KV cache budget management |

***

## Phase 0 — Foundations and Scaffolding

**Goal**: Lock the app shell, design tokens, typed contracts, mock fixtures, and quality gates before any feature work. Prevents all rework downstream .

### Deliverables

1. **App shell layout**: sidebar (collapsed 72px / expanded 248px), top bar (56px), content canvas, optional right inspector (384px). All dimensions from token values, not hardcoded.
2. **`tokens.css`**: all color, typography, spacing, radius, and motion values as CSS custom properties — exactly matching the design system specification.
3. **Core component primitives**: Button (Primary/Secondary/Tertiary/Destructive × Small/Medium/Large × all states), Input (Text/Search/Path/Secret/Select × all states), Tabs (Underline/Pill/Segmented), Badge/Chip/**StatusBadge** (all semantic colors — StatusBadge is a **separate** component from Badge, carrying the full run-state semantic color mapping), **Table** primitives (required — used by Runs list, Workspaces list, Secrets list), Panel, EmptyState, Banner, Modal, Drawer, Skeleton.
4. **MSW mock fixtures**: for all API routes — runs, events, workspaces, traces, plugins, MCP, browser events, secrets. Fixture shapes must mirror live OpenHands payload shapes exactly.
5. **Frontend route skeleton**: all routes rendered from mock data, with correct layout nesting and navigation.
6. **Storybook 10.4.6**: all core components documented with all variants and states.
7. **Playwright smoke harness**: shell renders, all routes resolve, sidebar navigation works, command palette opens.
8. **BFF scaffold**: FastAPI app with all router stubs, `loop_guard.py`, `context_loader.py`, `episodic_memory.py`, `conflict_checker.py`, and `model_router.py` with Ollama-first / vLLM-fallback logic.

### Phase 0 Open Items (as of July 13, 2026 Audit)

The following Phase 0 deliverables are scaffolded but **not yet complete**:

| Item | Status | Notes |
|------|--------|-------|
| `.openhands/` context directory | ❌ Missing | Create `architecture.md`, `conventions.md`, `decisions/001`, `decisions/002`, `personas/target-user.md` |
| MSW mock fixtures | ❌ Missing | Create fixture files in `src/tests/fixtures/` |
| Zod schemas | ❌ Missing | Populate `src/lib/schemas/` with typed schemas for all 9 domain objects |
| `Table` core component | ❌ Missing | Create `Table.tsx`, `Table.module.css`, `Table.stories.tsx` |
| `StatusBadge` component | ❌ Missing | Create as a distinct component from `Badge` with run-state semantic color map |
| Next.js API route stubs | ❌ Missing | Create stub `route.ts` files in `src/app/api/` |
| Storybook version | ⚠️ v8 installed | `package.json` has `^8.6.14`; spec requires `^10.4.6` — upgrade before Phase 1 |

### Exit Criteria

- All base layouts render from mock data with zero live service dependency.
- Every component supports: default, hover, focus, disabled, loading, error states.
- Shell is correct at 1280px, 1440px, and 1920px breakpoints.
- Token values match design system specification exactly.
- Zero TypeScript errors, zero ESLint errors.
- Ollama connection test passes with `devstral-small:24b`.
- All Phase 0 Open Items above are resolved.

### Agent Prompt

```
Implement Phase 0: Foundations.
Create the Next.js 16 App Router app shell: sidebar (72px collapsed, 248px expanded),
topbar (56px), content canvas, right inspector (384px).
Generate tokens.css with all color, typography, spacing, radius, and motion tokens
using exact values from the design specification.
Build core component primitives: Button, Input, Tabs, Badge, StatusBadge, Table,
Panel, EmptyState, Banner, Modal, Drawer, Skeleton.
StatusBadge is a SEPARATE component from Badge — it maps all run states
(idle/running/streaming/paused/awaiting_approval/succeeded/failed/blocked) to
their canonical state tokens.
Generate MSW fixtures for runs, events, workspaces, plugins, mcp, secrets.
Set up Storybook 10.4.6 with stories for all core components showing all variants and states.
Set up Playwright smoke tests for layout and navigation.
Scaffold the FastAPI BFF with router stubs and service stubs for loop_guard,
context_loader, episodic_memory, conflict_checker, and model_router.
Model router must implement Ollama-first (devstral-small:24b or qwen3:14b)
with vLLM fallback at localhost:8000.
Use ONLY the exact token names and component names from the design spec.
Do NOT implement any live data fetching in this phase.
```

***

## Phase 1 — Run Supervision MVP

**Goal**: Give users a real end-to-end experience for launching a run, watching it stream live, and inspecting events. Makes Forge-OH immediately useful as a thin supervision console .

### Slice 1A — Runs Home and Launcher

**User story**: A user can create a run from a task prompt, choose an agent preset and workspace, and see that run appear in the runs list.

**Frontend scope**:
- Runs home page with recent runs table: status chip, workspace chip, agent, cost, duration, updated-at
- New run composer: task input, agent preset selector, workspace selector
- Basic filters: workspace type, status, search text
- Empty state, loading skeleton, create-run error state, disabled state when no workspace

**BFF/API contracts**:
- `GET /api/runs` — list runs
- `POST /api/runs` — create run
- `GET /api/agents/presets` — list agent presets
- `GET /api/workspaces` — list workspaces

**Acceptance criteria**:
- User can launch a run from the home screen
- New run appears with optimistic state immediately, updates after backend confirmation
- Run creation is disabled when no workspace is available

### Slice 1B — Run Detail with Event Timeline

**User story**: A user can open a run and observe a summary-first event stream with current status, active tool, and most recent activity.

**Frontend scope**:
- Three-pane run detail layout: left plan rail, center timeline, right inspector
- Sticky run header: title, agent preset, workspace chip, active tool badge, elapsed time, cost, status
- Event timeline using `EventCard`: summary-first, expandable raw output, newest briefly highlighted
- Right inspector panel with selected event structured detail
- Stream connection banner: Streaming / Disconnected / Reconnecting

**BFF/API + Streaming contracts**:
- `GET /api/runs/:id` — run metadata
- `GET /api/runs/:id/events` — bootstrap event history
- `WS /runs/:id/stream` — Socket.IO with `oh_event` messages

**Streaming flow** :
1. Load metadata + bootstrap event history over HTTP
2. Connect Socket.IO with `conversation_id` + `latest_event_id`
3. Receive `oh_event` → validate → normalize → patch timeline and run status
4. On disconnect: reconnect with latest known `event_id` to avoid duplicates

**Acceptance criteria**:
- Run detail page updates live without page refresh
- Newest event is briefly highlighted on arrival
- Selected event populates inspector with structured detail

### Slice 1C — Plan Rail and Run Controls

**User story**: A user can see a plan step tree, understand progress, and invoke run controls.

**Frontend scope**:
- Left plan rail with `PlanNode` components (all 6 states: Queued/Active/Done/Failed/Blocked/AwaitingApproval)
- Run control buttons in sticky header: Pause, Stop, Fork, Retry-from-step, Approve-pending
- Approval waiting banner: amber, full-width, unmissable, in both header and timeline

**BFF/API contracts**:
- `POST /api/runs/:id/pause`
- `POST /api/runs/:id/resume`
- `POST /api/runs/:id/stop`

**Acceptance criteria**:
- Controls are visible and correctly stateful during streaming
- Plan node statuses update from stream events
- Paused and awaiting-approval states are visually distinct and unmissable

### Phase 1 Exit Criteria

- Users can create a run and supervise it live
- The UI establishes a stable mental model: Run → Plan → Event → Artifact
- Forge-OH is already useful as a thin supervision console

***

## Phase 2 — Code, Terminal, and Artifact Review

**Goal**: Add the surfaces that make Forge-OH a real code supervision tool: file diffs, command inspection, and exportable artifacts .

### Slice 2A — File Changes and Diff Review

**Frontend scope**:
- Files tab with `FileChangeItem` list: Added/Modified/Deleted/Renamed, add/remove counts, semantic summary
- `DiffHeader` with approve/reject/comment actions
- Monaco diff viewer (split or unified mode)
- Export patch button
- States: no file changes, binary/non-renderable, diff load failure

**BFF/API contracts**:
- `GET /api/runs/:id/artifacts/files`
- `GET /api/runs/:id/artifacts/diff?path=`
- `GET /api/runs/:id/export/patch`

**Acceptance criteria**:
- Users can browse changed files and render diffs
- Export patch returns a valid patch bundle
- Binary files degrade gracefully with a clear message

### Slice 2B — Terminal and Command Inspection

**Frontend scope**:
- Terminal tab with `@xterm/xterm` surface (streaming output)
- `CommandBlock`: command text, cwd, exit code, duration, risk level chip, stdout/stderr preview
- Agent-commands tab vs. manual terminal tab
- Secret-masked output handling (never expose raw values)

**BFF/API contracts**:
- `GET /api/runs/:id/commands`
- `GET /api/runs/:id/commands/:commandId/output`

**States**: Running command, truncated output, failed command, secret-masked output

**Acceptance criteria**:
- Commands stream or refresh correctly
- Error output is visually distinct (red stderr via `--color-terminal-stderr`)
- Risk scoring chip visible inline on each `CommandBlock`

### Slice 2C — Artifact Rail and Export Flow

**Frontend scope**:
- Artifact side rail or inspector section
- Preview cards grouped by type: file, diff, patch, image, report, download
- Download/export actions per artifact

**BFF/API contracts**:
- `GET /api/runs/:id/artifacts`
- `GET /api/runs/:id/artifacts/:artifactId`

**Acceptance criteria**:
- Artifacts grouped by type and discoverable
- Download actions reliable
- Missing previews degrade gracefully

### Phase 2 Exit Criteria

- Users can inspect what changed and what executed
- Forge-OH supports real code-review-like workflows
- Runs produce usable, exportable outputs

***

## Phase 3 — Environment, Integrations, and Governance

**Goal**: Expose workspaces, plugins, MCP servers, and secrets .

### Slice 3A — Workspaces Management

**Frontend scope**:
- Workspaces page with `WorkspaceCard` (local / docker / remote_api types)
- Health indicators: Healthy / Warning / Error / Disconnected
- Workspace details drawer: isolation mode, file upload/download, agent server URL
- Reset, duplicate, delete actions

**BFF/API contracts**:
- `GET /api/workspaces`
- `GET /api/workspaces/:id`
- `POST /api/workspaces/:id/reset`

**Acceptance criteria**:
- Workspace type is visually obvious everywhere in the app
- Runs link back to their workspace detail
- Health states use text + icon labels, not color alone (accessibility)

### Slice 3B — MCP Servers and Plugins

**Frontend scope**:
- Tools & MCP page with `MCPServerCard`: Connected/Warning/Disconnected, tool count, auth state, last call, error message
- Plugins page with `PluginCard`: Installed/Enabled/Disabled/UpdateAvailable/Error
- Enable/disable toggles; auth state warnings

**BFF/API contracts**:
- `GET /api/integrations/mcp`
- `GET /api/plugins`
- `POST /api/plugins/:id/enable`
- `POST /api/plugins/:id/disable`

**Acceptance criteria**:
- Integration health visible at a glance
- Failure states explain the next action, not just the failure

### Slice 3C — Secrets and Protected Configuration

**Frontend scope**:
- Secrets page with `SecretRow` (always masked values — never expose raw)
- Add/edit secret modal with scope selector
- Destructive actions require explicit confirmation modal

**BFF/API contracts**:
- `GET /api/secrets` — metadata + `maskedValue` only, never raw values
- `POST /api/secrets`
- `PATCH /api/secrets/:id`
- `DELETE /api/secrets/:id`

**Security rule**: Secret values must never reach the browser. BFF redacts all raw values before returning .

**Acceptance criteria**:
- Secret values always masked; raw values never appear in browser
- Scope conflicts surface clearly
- Deletion requires confirmation modal

### Phase 3 Exit Criteria

- Users understand and manage environment and extension surfaces
- Forge-OH is operationally credible for real teams

***

## Phase 4 — Browser Automation, Observability, and Deep Tracing

**Goal**: Surface the advanced OpenHands capabilities: browser automation and OTEL tracing .

### Slice 4A — Browser Session View

**Frontend scope**:
- Browser tab with `BrowserSessionCard` (Idle/Navigating/Interacting/Extracting/Failed)
- Live viewport preview (base64 screenshot stream from `BrowserScreenshotAction`)
- Navigation step history: URL, click, type, scroll, extract events
- Extracted content section

**BFF/API contracts**:
- `GET /api/runs/:id/browser/sessions`
- `GET /api/runs/:id/browser/sessions/:sessionId`

**States**: No browser activity, navigation in progress, extraction complete, browser failure, screenshot unavailable

**Acceptance criteria**:
- Browser events visually distinct from terminal events
- User can reconstruct the browsing flow from the UI
- Screenshot previews degrade gracefully

### Slice 4B — Observability Dashboard

**Frontend scope**:
- Observability page with `MetricTile`: run cost, duration, token usage, error rates, tool frequency
- Trend charts with Recharts
- Slowest runs and most expensive runs tables
- Drill-down links into run detail

**BFF/API contracts**:
- `GET /api/observability/summary`
- `GET /api/observability/runs`
- `GET /api/observability/errors`

**Acceptance criteria**:
- Global KPIs load quickly
- Drill-down paths to runs preserved
- Empty/sparse data looks intentional, not broken

### Slice 4C — Trace Explorer

**Frontend scope**:
- Trace explorer with `TraceSpanRow` (LLM/Tool/Workspace/Browser/Network/System span types)
- Span tree expansion with parent-child depth visualization
- Filters by span type and error status
- Link from trace span to associated `EventCard`

**BFF/API contracts**:
- `GET /api/runs/:id/traces`
- `GET /api/runs/:id/traces/:spanId`

**Acceptance criteria**:
- Span tree navigable at depth
- Error spans easy to find via filter
- Span selection links back to event timeline

### Phase 4 Exit Criteria

- Forge-OH supports genuine debugging and postmortem analysis
- Browser and tracing workflows feel first-class
- The GUI exposes the major OpenHands SDK differentiators

***

## Phase 5 — Refinement, Safety, and Rigpa-LMS Plugin Foundation

**Goal**: Harden for agentic self-building, ship approval/intervention flows, and establish the Rigpa-LMS plugin integration layer .

### Slice 5A — Approval and Intervention Flows

**Frontend scope**:
- Approval banners and modal flows: amber, full-width, unmissable
- Awaiting-approval detail view with context about what triggered the pause
- Intervention history in run timeline

**BFF/API contracts**:
- `POST /api/runs/:id/approve`
- `POST /api/runs/:id/reject`

**Acceptance criteria**:
- Approval states unmissable — never buried in event stream
- Resolution history visible in timeline
- Rejection creates a meaningful follow-up state, not a dead end

### Slice 5B — Replay, Fork, and Compare

**Frontend scope**:
- Fork action in run header and plan nodes
- Compare view for artifacts and summary metadata (side-by-side diff, duration, outcome)

**BFF/API contracts**:
- `POST /api/runs/:id/fork`
- `GET /api/runs/compare?left=&right=`

**Acceptance criteria**:
- Fork creates a new run linked to the original
- Comparison shows changed files, durations, and outcomes side by side

### Slice 5C — Rigpa-LMS Plugin Integration Layer

This slice transforms Forge-OH from a standalone tool into a Rigpa-LMS embedded panel .

**LMS context injection interface**:

```typescript
interface RigpaAgentLaunchContext {
  userId: string
  courseId: string
  moduleId?: string
  lessonId?: string
  repoUrl?: string
  workspacePath?: string
  taskType: 'authoring' | 'exercise-gen' | 'code-review' | 'assessment' | 'refactor'
  permissions: {
    canWriteRepo: boolean
    canRunShell: boolean
    canOpenPR: boolean
  }
  pedagogicalContext: {
    audience: 'beginner' | 'intermediate' | 'advanced'
    learningGoals: string[]
    styleGuide?: string
  }
}
```

The plugin sends this to the Forge BFF, which transforms it into an OpenHands task context and policy envelope. Every agent session is reproducible and auditable within the LMS context.

**LMS context ribbon** (always visible in plugin mode):
- Course name + lesson/module indicator
- Assignment type selector: Generate Exercise / Review Code / Author Content / Assessment / Refactor
- Audience level chip: Beginner / Intermediate / Advanced

**Artifact-to-LMS packaging**:

| Forge-OH Action | LMS Artifact Output |
|----------------|---------------------|
| Agent writes code problem + solution + tests | LMS exercise object with rubric |
| Agent reviews submission against rubric | Feedback record with per-criterion scores |
| Agent drafts lesson text, diagrams, examples | Lesson content block |
| Agent sets up boilerplate project | Starter kit assignment |
| Agent generates progressive hints | Hint sequence attached to exercise |
| Agent writes quiz from course material | Quiz object |

**Identity mapping**:
- LMS user ID → Forge session and policy profile
- LMS role (instructor/student) → tool permission policy
- Course enrollment → workspace access control

**Acceptance criteria**:
- LMS launch context serialized and injected into every agent task preamble
- LMS ribbon always visible at the top of the plugin panel
- Artifacts can be packaged back to LMS as course objects
- Plugin embeddable in an LMS iframe or panel without layout breakage

### Slice 5D — Build-System Hardening for AI Agent Execution

**Goal**: Ensure the repository is optimized for Perplexity Computer and Claude Code as implementation agents .

**Requirements**:
- Every route has a README or inline contract note
- Every component has a single source of truth for props and states
- Every domain object has a typed Zod schema
- Mock fixtures mirror live payload shapes exactly
- Each slice has a task checklist, acceptance criteria, and test plan
- Feature flags isolate unfinished slices: `FEATURE_[SLICE_NAME]_ENABLED`
- Seed data supports deterministic screenshot and interaction testing

### Slice 5E — Model Router Hardening

**Goal**: Ensure Ollama-first / vLLM-fallback routing is robust, observable, and tunable .

**BFF `model_router.py`** logic:

```python
import os

DEVSTRAL_MODEL = os.getenv("DEVSTRAL_MODEL", "devstral-small:24b")
FAST_MODEL     = os.getenv("FAST_MODEL",     "qwen3:14b")
VLLM_FALLBACK_MODEL = os.getenv("VLLM_FALLBACK_MODEL", "mistral:7b")
DEVSTRAL_CTX_LIMIT  = 28_000  # KV cache budget for Devstral 24B on RTX 5070

async def route_request(task_complexity: str, context_length: int) -> str:
    """Route to optimal local model. Never hardcode model names — use env vars."""
    if context_length > DEVSTRAL_CTX_LIMIT:
        # Devstral 24B has no KV cache headroom — route to Qwen3 14B or vLLM
        return await try_model(FAST_MODEL, fallback=VLLM_FALLBACK_MODEL)
    if task_complexity == "agentic":
        return await try_model(DEVSTRAL_MODEL, fallback=VLLM_FALLBACK_MODEL)
    return await try_model(FAST_MODEL, fallback=VLLM_FALLBACK_MODEL)

async def try_model(primary: str, fallback: str) -> str:
    if await ollama_health_check(primary):
        return f"ollama/{primary}"
    resolved_fallback = fallback or VLLM_FALLBACK_MODEL
    if await vllm_health_check():
        return f"vllm/{resolved_fallback}"
    raise ModelUnavailableError("No local LLM available")
```

***

## Accessibility Standards (Non-Negotiable)

Forge-OH must meet WCAG 2.1 AA as a core product requirement :

- Full keyboard navigation and command palette access (`Cmd+K`)
- Screen-reader labels on all action buttons and status chips
- Visible focus rings: 2px solid `--color-accent-primary`
- Reduced-motion support via `@media (prefers-reduced-motion)` on all streaming animations
- Status conveyed by text + icon, never color alone
- Minimum 4.5:1 contrast ratio for body text on dark backgrounds
- Readable monospace text for commands, diffs, and trace identifiers (minimum 12px)

***

## Definition of Done (Every Slice)

A slice is done only when all of the following are true :

- [ ] UI implementation complete
- [ ] Typed data contract (TypeScript interfaces + Zod schemas)
- [ ] Mock fixture that mirrors live payload shape exactly
- [ ] Loading state
- [ ] Empty state
- [ ] Error and degraded state
- [ ] Basic instrumentation hook
- [ ] Responsive verification (1280px, 1440px, 1920px)
- [ ] Accessibility pass (keyboard nav, labels, contrast)
- [ ] Automated test coverage for critical path (unit + integration + E2E)
- [ ] Feature flag gating `FEATURE_[SLICE_NAME]_ENABLED`

***

## Agent Prompting Protocol

Use this exact format when assigning a slice to Perplexity Computer or Claude Code :

```
Implement [Phase N, Slice NA]: [Slice Name].

Routes: [exact route list]
Components: [exact component names from domain model]
BFF contracts: [exact API routes]
States to handle: [loading, empty, error, degraded, streaming — list all]
Acceptance criteria: [verbatim from spec]
Tests required: [unit + integration + E2E minimum]

Constraints:
- Use only existing design tokens — no new token names.
- Use only existing component names — no new visual language.
- All states must be handled explicitly.
- Mock fixtures must mirror live payload shapes exactly.
- Do not modify the app shell or layout system.
- Feature flag this slice with FEATURE_[SLICE_NAME]_ENABLED.
- Model routing: Ollama devstral-small:24b primary, qwen3:14b for long context,
  vLLM fallback. Never hardcode model names in frontend.
- BFF must be started with: uvicorn bff.main:app_with_sio (NOT bff.main:app).
```

***

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| OpenHands agent loop getting stuck | High | Medium | `loop_guard.py` in BFF; escalation path; pause/resume  |
| Context window degradation on long runs | Medium | High | `episodic_memory.py`; route long context to Qwen3 14B  |
| Merge conflicts in agentic PRs | High | Medium | `conflict_checker.py` pre-PR; auto-resolution for simple cases  |
| Frontend coupling to raw OpenHands payloads | Medium | High | BFF contract layer normalizes all upstream shapes  |
| Self-building agent modifying control plane | Low | Critical | Control/target plane separation; protected path classes  |
| VRAM exhaustion on RTX 5070 | Medium | High | KV cache budget routing; never below Q4_K_M  |
| LMS context injection latency | Low | Medium | Cache `RigpaAgentLaunchContext` per session; async injection  |
| Secret exposure in browser | Low | Critical | BFF redaction layer; masked values only; raw values never returned  |
| TS 6.0 strict mode breaking changes | Medium | Medium | Run `tsc --noEmit` before CI gates; fix all strict errors first  |
| Ollama unavailable / GPU busy | Medium | High | vLLM fallback; health check in model_router.py  |
| Socket reconnect storm (callback instability) | Medium | High | Wrap all `useRunStream` callbacks in `useRef` before use in `useEffect` deps |

***

## Rigpa-LMS Integration Roadmap

| Phase | Milestone |
|-------|----------|
| **Now (Slices 0–4)** | Standalone Forge-OH console: connect to local OpenHands, open repo, show chat + plan + files + diff + terminal, inject one course context packet |
| **Phase 5C** | LMS plugin integration: `RigpaAgentLaunchContext`, course ribbon, pedagogical modes, artifact-to-LMS packaging |
| **Future Phase 6** | LMS-aware orchestration: role-based permissions, saved prompt templates (lesson gen, rubric gen, code review), artifact return into LMS objects |
| **Future Phase 7** | First-class Rigpa-LMS plugin: iframe or native panel, SSO/session handoff, per-course workspaces, instructor dashboards, audit history |
| **Future Phase 8** | Autonomous workflows: scheduled course repo maintenance, batch exercise generation, student submission review queues, PR creation and approval workflows |

***

## Audit & Fixes Log

### Phase 0 Audit — July 13, 2026

Multi-pass audit of the `rmholston420/forge-oh` repo against this build plan. Code was read directly from the repository and treated as ground truth over any prior log entries.

#### Verified Correct (Phase 0 Scaffold)

| Area | Finding |
|------|---------|
| `package.json` frontend deps | All spec versions present and correctly pinned |
| `src/styles/tokens.css` | All design tokens match spec exactly |
| BFF services (5/5) | `loop_guard`, `context_loader`, `episodic_memory`, `conflict_checker`, `model_router` all present |
| BFF routers | All required routers present; `lms.py` and `notifications.py` scaffolded ahead of schedule |
| Dashboard routes | All 8 spec routes present |
| Core component library | Button, Input, Badge, Banner, Tabs, Modal, Drawer, Skeleton, Panel, EmptyState — all with `.tsx`, `.module.css`, `.stories.tsx` triads |
| Feature slice directories | All 18 slices scaffolded (plus bonus `run-replay`) |
| `useRunStream.ts` | Correct 5-step streaming flow; `approval_required` event handled |
| Dashboard shell | Sidebar/Topbar/CommandPalette/AuthGuard wired correctly; `⌘K` shortcut implemented |

#### Bugs Fixed (confirmed in live code)

| Bug | File | Fix Applied |
|-----|------|------------|
| Loop guard off-by-one (detected on 4th hit, not 3rd) | `bff/services/loop_guard.py` | Append-before-count order corrected; reference impl in this document updated to match |
| vLLM fallback model hardcoded as literal `"vllm"` | `bff/services/model_router.py` | `VLLM_FALLBACK_MODEL` env var added; `try_model()` uses resolved value |
| ASGI entry point undocumented (`app` vs `app_with_sio`) | `bff/main.py` | `app_with_sio` now documented with prominent warning comment; added to this document |
| CORS + credentials conflict (`allow_origins=["*"]` + `allow_credentials=True`) | `bff/main.py` | Fixed in live code |

#### Open Gaps (Phase 0 not yet complete)

See the **Phase 0 Open Items** table above. These must be resolved before any Phase 1 slice begins.

#### Positive Deviations (Beyond Spec)

- `src/features/rigpa-lms/` scaffolded early (Slice 5C ahead of schedule)
- `src/features/run-replay/` bonus feature not in the 18-slice plan
- `src/lib/feature-flags/`, `src/lib/rbac/`, `src/lib/plugins/` present beyond Phase 0 requirements
- `LoopGuard.reset()` method added (useful, not in original spec)
