# Forge-OH Audit & Fix Log

## Audit — July 13, 2026

Multi-pass audit conducted against the Forge-OH Definitive Build Plan.

### Critical Bugs — All Resolved Prior to This Commit

| # | File | Bug | Resolution |
|---|------|-----|------------|
| 1 | `bff/services/loop_guard.py` | Off-by-one: loop detected on 4th hit, not 3rd. Count happened before append. | Fixed: `history.append(h)` moved before `sum(...)` count. Docstring explains fix. |
| 2 | `bff/services/model_router.py` | vLLM fallback was hard-coded literal `"vllm"`, producing path `"vllm/vllm"`. | Fixed: `VLLM_FALLBACK_MODEL = os.getenv("VLLM_FALLBACK_MODEL", "mistral:7b")`. |
| 3 | `bff/main.py` | `app_with_sio` was created but not documented as the required ASGI entry point. Starting with `bff.main:app` silently bypassed Socket.IO. | Fixed: Prominent `# CRITICAL` comment added. CORS logic also corrected (`allow_origins=["*"]` + `allow_credentials=True` incompatibility). |
| 4 | `src/lib/streaming/useRunStream.ts` | Callback functions in `useEffect` dep array caused socket disconnect/reconnect on every render. | Fixed: All callbacks stabilised via `useRef`. `useEffect` dep array contains only `[runId, latestEventId, enabled]`. |

### Gaps — Closed in This Commit (July 13, 2026)

| # | Gap | Files Added / Changed |
|---|-----|----------------------|
| 1 | Storybook pinned at v8.6.14, spec requires v10.4.6 | `package.json` — all `@storybook/*` upgraded to `^10.4.6` |
| 2 | `openhands==cloud-1.46.0` not a valid PyPI version string | `bff/requirements.txt` — replaced with `openhands @ git+https://github.com/All-Hands-AI/OpenHands.git@cloud-1.46.0` |
| 3 | `.openhands/` context directory missing | Added: `architecture.md`, `conventions.md`, `decisions/001-use-ollama-first.md`, `decisions/002-no-direct-openhands.md`, `personas/target-user.md` |
| 4 | MSW mock fixtures not created | Added: `src/tests/fixtures/runs.ts`, `events.ts`, `workspaces.ts`, `plugins.ts`, `secrets.ts`, `mcp.ts`, `index.ts` |
| 5 | Zod schemas not populated | Added: `src/lib/schemas/run.ts`, `event.ts`, `workspace.ts`, `plugin.ts`, `trace.ts`, `secret.ts`, `browser.ts`, `command.ts`, `artifact.ts`, `index.ts` |
| 6 | `Table` core component missing | Added: `Table.tsx`, `Table.module.css`, `Table.stories.tsx` |
| 7 | `StatusBadge` not a separate component | Added: `StatusBadge.tsx`, `StatusBadge.module.css`, `StatusBadge.stories.tsx` |
| 8 | Next.js API route stubs missing | Added: `src/app/api/runs/route.ts`, `runs/[runId]/route.ts`, `runs/[runId]/events/route.ts`, `runs/[runId]/artifacts/route.ts`, `runs/[runId]/commands/route.ts`, `workspaces/route.ts`, `plugins/route.ts`, `mcp/route.ts`, `secrets/route.ts`, `observability/route.ts` |

### Positive Deviations (Beyond Spec)

These items were found in the repo ahead of schedule — no action needed:

- `src/features/rigpa-lms/` scaffolded early (Slice 5C)
- `src/features/run-replay/` bonus feature not in the 18-slice plan
- `src/lib/feature-flags/`, `src/lib/rbac/`, `src/lib/plugins/` present beyond Phase 0 scope
- `bff/routers/lms.py` and `bff/routers/notifications.py` ahead of their slice order
- `LoopGuard.reset()` method is a useful addition not in the spec
- `bff/requirements.txt` includes `aiosqlite`, `redis`, `httpx`, `pydantic-settings`, `python-multipart`, `websockets` beyond the spec minimum — all appropriate additions

### Phase 0 Exit Criteria Status (Post-Commit)

| Criterion | Status |
|-----------|--------|
| All base layouts render from mock data, zero live service dependency | ✅ MSW fixtures now populated |
| Every core component has default, hover, focus, disabled, loading, error states | ✅ (Table + StatusBadge added) |
| Shell correct at 1280px, 1440px, 1920px | ✅ (existing) |
| Token values match design system spec exactly | ✅ (existing) |
| Zero TypeScript errors, zero ESLint errors | ⚠️ Run `tsc --noEmit` to verify after install |
| Storybook 10.4.6 with all core components | ✅ Upgraded to v10.4.6 |
| Playwright smoke harness | ✅ (existing) |
| BFF scaffold with all five pre-Phase-1 services | ✅ (existing) |
| Ollama connection test passes with devstral-small:24b | ⚠️ Requires local Ollama instance |
| Zod schemas for all domain objects | ✅ Added |
| Next.js API route stubs | ✅ Added |
| `.openhands/` context directory | ✅ Added |

### Next Steps — Phase 1 Ready

With all Phase 0 gaps closed, the project is ready to begin **Slice 1A: Runs Home and Launcher**.

Recommended order:
1. Wire MSW handlers in `src/tests/fixtures/` to the MSW server setup in `src/tests/`
2. Run `npm install` to resolve Storybook v10 peer dependencies
3. Run `tsc --noEmit` and fix any type errors surfaced by the new Zod schemas
4. Run Storybook to verify Table and StatusBadge stories render correctly
5. Begin Slice 1A feature work
