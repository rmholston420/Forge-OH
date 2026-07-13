# Forge-OH — Canonical Domain Model

> **Rule:** Every frontend contract, API route, mock fixture, Zod schema,
> TypeScript interface, and agent context must use these exact names.
> Never rename, abbreviate, or alias these objects.

## First-Class Domain Objects

| Object | Purpose |
|--------|---------|
| `Run` | One live or historical execution session; maps to an OpenHands conversation |
| `AgentPreset` | Reusable behavior model: tools, policies, skills, model selection |
| `Workspace` | Execution environment: `local`, `docker`, or `remote-api` |
| `ToolEvent` | Single action, observation, browser step, or file operation |
| `Artifact` | File change, patch, screenshot, report, or downloadable output |
| `Integration` | MCP server, plugin, endpoint, or external system |
| `TraceSpan` | OTEL record for LLM, tool, workspace, browser, or network |
| `SecretRef` | Secret metadata only — raw values **never** in UI |
| `PlanNode` | One step in an agent task decomposition tree |
| `CommandExecution` | Shell command: text, cwd, exit code, duration, risk level |
| `BrowserSession` | Browser automation session: URL, step history, viewport |

## Run Status State Machine

| Status | Token | Color |
|--------|-------|-------|
| `idle` | `--color-text-tertiary` | Grey |
| `running` | `--color-state-running` | Blue |
| `streaming` | `--color-accent-primary` | Blue |
| `queued` | `--color-state-paused` | Purple |
| `paused` | `--color-state-paused` | Purple |
| `awaiting-approval` | `--color-state-warning` | Amber |
| `succeeded` | `--color-state-success` | Green |
| `failed` | `--color-state-error` | Red |
| `blocked` | `--color-state-error` | Red |
| `disconnected` | `--color-state-error` | Red |

## PlanNode States

`queued` → `active` → `done` | `failed` | `blocked` | `awaiting-approval`

## Workspace Types

`local` | `docker` | `remote-api`

## TaskType (Rigpa-LMS)

`authoring` | `exercise-gen` | `code-review` | `assessment` | `refactor`
