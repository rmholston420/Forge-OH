# Forge-OH Coding Conventions

## Domain Object Naming (Never Rename)

All frontend contracts, API routes, mock fixtures, and agent context must use these exact names:

| Object | Purpose |
|--------|---------|
| `Run` | One live or historical execution session |
| `AgentPreset` | Reusable behavior: model, tools, policies, skills |
| `Workspace` | Execution environment: local, docker, remote_api |
| `ToolEvent` | Single action, observation, browser step, or file operation |
| `Artifact` | File change, patch, screenshot, report, downloadable output |
| `Integration` | MCP server, plugin, endpoint, external system |
| `TraceSpan` | OTEL record for LLM, tool, workspace, browser, network |
| `SecretRef` | Metadata only — raw values never in UI |
| `PlanNode` | One step in an agent task decomposition tree |
| `CommandExecution` | Shell command: text, cwd, exit code, duration, risk level |
| `BrowserSession` | Browser automation session: URL, step history, viewport |

## TypeScript Rules

- `strict: true` is always on — never use `any` or `// @ts-ignore`
- Run `tsc --noEmit` before every commit
- All API contracts are validated with Zod schemas in `src/lib/schemas/`
- No direct OpenHands SDK imports in frontend — all via BFF proxy

## API Conventions

- All BFF routes are prefixed `/api/`
- Run operations: `/api/runs`, `/api/runs/:id`, `/api/runs/:id/events`
- All responses follow `{ data, error, meta }` envelope pattern
- Pagination uses `cursor`-based pagination, not offset

## Component Conventions

- Every core component has three files: `.tsx`, `.module.css`, `.stories.tsx`
- Domain components live in `src/components/domain/`
- Feature logic lives in `src/features/<slice>/`
- Shared utilities live in `src/lib/`

## Design Token Rules

- **Never hardcode colors, spacing, or font sizes**
- All values must reference CSS custom properties from `src/styles/tokens.css`
- State colors are semantic: use `--color-state-running`, `--color-state-error`, etc.
- Never invent new token names — only use tokens defined in the spec

## Secret Handling

- Raw secret values are NEVER in the UI, NEVER in logs
- `SecretRef` objects carry metadata only (name, type, last-rotated)
- Terminal output with secrets is masked before display
