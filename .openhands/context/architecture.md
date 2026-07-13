# Forge-OH Architecture

## Overview

Forge-OH is a browser-based, workspace-centered agent operations console built on the OpenHands SDK. It is a supervision-first control plane for autonomous software engineering agents, not a generic AI chat interface.

## Four-Layer Architecture

```
┌──────────────────────────────────────────────────────┐
│  Rigpa-LMS Plugin Shell (Phase 5C)                    │
│  Auth · Permissions · Course Context · LMS Exchange   │
├──────────────────────────────────────────────────────┤
│  Forge-OH Frontend                                    │
│  Next.js 16 App Router · Zustand 5 · TanStack Q 5    │
│  Socket.IO 4.8 · Monaco 0.55 · xterm 5.5             │
├──────────────────────────────────────────────────────┤
│  Forge BFF / Orchestration Service                    │
│  FastAPI 0.136 · Pydantic 2.12 · Python 3.13         │
│  context_loader · loop_guard · episodic_memory        │
│  conflict_checker · model_router                      │
├──────────────────────────────────────────────────────┤
│  OpenHands Agent Server (cloud-1.46.0)                │
│  Ollama v0.31.2 (primary) · vLLM v0.25.0 (backup)    │
│  Docker workspaces · REST/WS APIs                     │
└──────────────────────────────────────────────────────┘
```

## Critical Rule

**The frontend NEVER talks directly to OpenHands.** All traffic flows through the BFF. The BFF is the sole policy injection point for:
- Course context from Rigpa-LMS
- Loop-guard enforcement
- Episodic memory recall
- Delegation contract templates
- Model routing (Ollama-first, vLLM fallback)

## Five First-Class Domain Objects

Every design and implementation decision must trace back to these objects:

1. **Run** — one live or historical execution session
2. **Agent** — reusable behavior preset (model, tools, policies, skills)
3. **Workspace** — execution environment (local, docker, remote_api)
4. **Tool** — MCP server, plugin, or built-in capability
5. **Artifact** — file change, patch, screenshot, report, downloadable output

## State Management

| Layer | Technology | Owns |
|-------|-----------|------|
| Server truth | TanStack Query | Runs, workspaces, plugins, MCP status, secrets metadata |
| Stream truth | Socket.IO → Zustand | Live events, status changes, file mutations, approval events |
| UI truth | Zustand | Selected tab, collapsed panes, filter text, pending banners |

## Self-Building Safety

Control plane (running Forge-OH) is strictly separated from the target plane (the branch the agent modifies). Self-changes require: plan approval → code generation in isolated target → human diff review → automated checks pass → merge/promote.
