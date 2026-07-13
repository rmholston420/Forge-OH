# Forge-OH Architecture

Forge-OH is a browser-based, workspace-centered agent operations console built on the OpenHands SDK.

## Four-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Rigpa-LMS Plugin Shell (Phase 5C)                   │
│  Auth · Permissions · Course Context · LMS Exchange  │
├─────────────────────────────────────────────────────┤
│  Forge-OH Frontend                                   │
│  Next.js 16 App Router · Zustand 5 · TanStack Q 5   │
│  Socket.IO 4.8 · Monaco 0.55 · xterm 5.5            │
├─────────────────────────────────────────────────────┤
│  Forge BFF / Orchestration Service                   │
│  FastAPI 0.136 · Pydantic 2.12 · Python 3.13        │
│  context_loader · loop_guard · episodic_memory       │
│  conflict_checker · model_router                     │
├─────────────────────────────────────────────────────┤
│  OpenHands Agent Server (cloud-1.46.0)               │
│  Ollama v0.31.2 (primary) · vLLM v0.25.0 (backup)   │
│  Docker workspaces · REST/WS APIs                    │
└─────────────────────────────────────────────────────┘
```

## The Single Most Important Architectural Rule

**The frontend never talks directly to OpenHands. All traffic flows through the BFF.**

The BFF is the policy injection point for:
- Course context injection (context_loader)
- Loop-guard enforcement (loop_guard)
- Episodic memory recall (episodic_memory)
- Conflict detection before PRs (conflict_checker)
- Model routing (model_router — Ollama-first, vLLM fallback)

## Five First-Class Domain Objects

Every design and implementation decision must trace back to:
1. **Run** — one live or historical execution session
2. **Agent** — reusable behavior preset (model, tools, policies, skills)
3. **Workspace** — execution environment (local, docker, remote_api)
4. **Tool** — MCP server, plugin, or integration
5. **Artifact** — file change, patch, screenshot, report, downloadable output

## State Management Three-Layer Separation

| Layer | Technology | Owns |
|-------|-----------|------|
| Server truth | TanStack Query | Runs list, metadata, workspaces, plugins, MCP status |
| Stream truth | Socket.IO → Zustand | Live oh_event messages, status changes, approval events |
| UI truth | Zustand | Selected tab, collapsed panes, filter text, diff mode |

## Self-Building Safety Model

- **Control plane** — the running Forge-OH instance the operator uses
- **Target plane** — the checked-out branch or Docker worktree the agent may modify

Self-changes gate: plan approval → code generation in isolated target → human diff review → automated checks pass → merge/promote.
