# Forge-OH

> Browser-based, workspace-centered agent operations console built on the OpenHands SDK.

Forge-OH is a **supervision-first control plane** for autonomous software engineering agents. It is not a generic AI chat interface — it is a structured environment for launching, monitoring, pausing, approving, and reviewing AI agent runs. It will eventually embed into Rigpa-LMS as a pedagogical coding copilot.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Rigpa-LMS Plugin Shell (Phase 5C)           │
├─────────────────────────────────────────────┤
│  Forge-OH Frontend                           │
│  Next.js 16 · Zustand 5 · TanStack Query 5  │
├─────────────────────────────────────────────┤
│  Forge BFF (FastAPI 0.136 · Python 3.13)    │
├─────────────────────────────────────────────┤
│  OpenHands cloud-1.46.0                      │
│  Ollama 0.31.2 · vLLM 0.25.0                │
└─────────────────────────────────────────────┘
```

**The single most important architectural rule: the frontend never talks directly to OpenHands. All traffic flows through the BFF.**

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16.2.10, Zustand 5, TanStack Query 5, Socket.IO 4.8, Monaco 0.55, xterm 5.5 |
| BFF | FastAPI 0.136.2, Pydantic 2.12, Python 3.13, python-socketio 5.11 |
| Agent | OpenHands cloud-1.46.0 |
| LLM (primary) | Ollama v0.31.2 — devstral-small:24b (agentic), qwen3:14b (fast/long-ctx) |
| LLM (fallback) | vLLM v0.25.0 |

## Getting Started

### Frontend

```bash
npm install
cp .env.example .env.local
npm run dev
```

> Note: `@hookform/resolvers` and `react-hook-form` are needed for NewRunComposer.
> Run `npm install react-hook-form @hookform/resolvers` to add them.

### BFF

```bash
cd bff
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn bff.main:app_with_sio --reload --port 8000
```

### Storybook

```bash
npm run storybook
```

### Tests

```bash
# Unit + integration
npm test

# E2E (requires dev server running)
npm run test:e2e
```

## Build Plan

| Phase | Status | Deliverable |
|-------|--------|-------------|
| **Phase 0** | ✅ Done | App shell, tokens, core components, MSW mocks, Storybook, E2E smoke |
| **Phase 1** | ✅ Done | Run supervision MVP — runs list, new run composer, run detail + streaming, plan rail, approval banner |
| **Phase 2** | 🚧 Next | Code, terminal, artifact review |
| **Phase 3** | ⏳ Planned | Workspaces, MCP, plugins, secrets |
| **Phase 4** | ⏳ Planned | Browser automation, observability, trace explorer |
| **Phase 5** | ⏳ Planned | Approvals, fork/compare, Rigpa-LMS integration, hardening |

## Five First-Class Objects

| Object | Purpose |
|--------|---------|
| `Run` | One live or historical execution session |
| `AgentPreset` | Reusable behavior: model, tools, policies |
| `Workspace` | Execution environment: local, docker, remote_api |
| `ToolEvent` | Single action, observation, or file operation |
| `Artifact` | File change, patch, screenshot, report, download |

## Feature Flags

All slices are gated behind feature flags (`NEXT_PUBLIC_FEATURE_[SLICE]_ENABLED`). See `.env.example` for all flags.

---

*Forge-OH will eventually be built by Forge-OH.*
