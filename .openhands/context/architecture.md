# Forge-OH Architecture

## Four-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Rigpa-LMS Plugin Shell (Phase 5C)                   │
├─────────────────────────────────────────────────────┤
│  Forge-OH Frontend                                   │
│  Next.js 16 App Router · Zustand 5 · TanStack Q 5   │
├─────────────────────────────────────────────────────┤
│  Forge BFF / Orchestration Service                   │
│  FastAPI 0.136 · Python 3.13                         │
├─────────────────────────────────────────────────────┤
│  OpenHands Agent Server (cloud-1.46.0)               │
│  Ollama v0.31.2 (primary) · vLLM v0.25.0 (backup)   │
└─────────────────────────────────────────────────────┘
```

## Non-Negotiable Rules

1. **The frontend NEVER talks directly to OpenHands.** All traffic through BFF.
2. **Secret values NEVER reach the browser.** BFF redacts all raw values.
3. **Model selection NEVER happens in the frontend.** BFF routes all LLM calls.
4. **Never go below Q4_K_M quantization.** Q3_K_S introduces code syntax errors.
5. **Control/target plane separation.** The running Forge-OH instance is never the agent's target.

## Five First-Class Objects

- **Run** — one live or historical execution session
- **AgentPreset** — reusable behavior: model, tools, policies
- **Workspace** — execution environment: local, docker, remote_api
- **ToolEvent** — single action, observation, or file operation
- **Artifact** — file change, patch, screenshot, report
