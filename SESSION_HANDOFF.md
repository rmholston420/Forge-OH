# Forge-OH Session Handoff — 2026-08-04 21:38 EDT

## Current build-sequencing position
- **Stage / phase:** Stage 1 · reconciliation-plan-v1 (sub-slices 1.1–1.7).
- **Slice branch:** `slice/stage1-reconciliation-v1` (pushed after this handoff writes).
- **Plugin / kernel component:** BFF (`bff/routers/runs.py`, `bff/services/event_relay.py`) + Next.js dashboard (MCP, Secrets, Agent Presets, Run Detail).
- **Port(s) touched:** none new. All BFF changes ride on the existing `/api` mount; Socket.IO changes ride on the existing sio server.

## Completed this session
- **1.1** — bumped `openhands-sdk` to `1.40.0` in `bff/requirements.lock`; added `typecheck` and `test:unit` script aliases in `package.json`.
- **1.2** — MCP `api.ts` `/api`-prefix bug fixed; `(dashboard)/tools-mcp/page.tsx` now renders real `McpPage`.
- **1.3** — Sidebar entry for `/secrets` added; stub `settings/secrets/page.tsx` deleted; 3 e2e specs redirected to `/secrets`.
- **1.4** — deleted 3 orphan Next.js API proxy routes; deleted dead Plugins scaffolding (`src/features/plugins/PluginsPage.tsx`, `src/lib/plugins/hooks.ts`) plus 2 orphan tests; deleted `src/lib/runs.ts`; removed `FEATURE_RIGPA_LMS_ENABLED` env var from `docker-compose.yml`; deleted `bff/routers/agents.py` deprecation stub.
- **1.5.2** — `(dashboard)/agents/page.tsx` now renders real `AgentPresetsPage`; `agent-presets/api.ts` `/api`-prefix bug fixed on all 7 fetches.
- **1.6** — full stack: `POST /runs/{run_id}/message` in `bff/routers/runs.py` (mirrors agent-server 1.40.0's `SendMessageRequest`/`TextContent`), `ENDPOINTS.RUNS.message`, `sendRunMessage` API, `useSendRunMessage` hook, and new `RunMessageComposer` component rendered persistently at the bottom of the run-detail page.
- **1.7** — `bff/services/event_relay.py` now emits a dedicated `"approval_required"` Socket.IO event with a proper `type` discriminator when a conversation enters `waiting_for_confirmation`, unblocking the previously-dead frontend listener in `useRunStream`.

## Remaining before current Definition of Done
- **Colossus runtime verify** (user's job per directive #2):
  - `bff/requirements.lock` full pip-compile regen on Colossus's actual Python venv (sandbox is 3.14).
  - `pnpm typecheck` — must be clean.
  - `pnpm test:unit` — must be clean.
  - `pnpm build` — must succeed.
  - `pytest --collect-only bff/tests/` — must be clean.
  - Playwright: `secrets.spec.ts`, `nav-routes.spec.ts`, `visual-tour.spec.ts` against `next start` on :3100.
  - Manual smoke: Tools MCP page loads, Agent Presets page loads, Secrets appears in sidebar, Send-Message composer submits during a live run, `approval_required` fires when a confirmation gate triggers.
- **Merge decision for 1.5.3–1.5.5** — see open question below.

## Open questions / awaiting user answer
1. **ADR-009 vs 1.5.3–1.5.5 — RESOLVED (option b).** Operator chose to supersede ADR-009 with a new dual-mode routing ADR: role-based routing remains canonical and takes precedence; preset-driven model override layers on top only when `preset.model` is compatible with the resident role's model. `AgentPreset` gains a `role: Literal["coder","planner"]` field. Next slice will draft `docs/adrs/ADR-0XX-dual-mode-routing.md` per `kosmos-adr-authoring` workflow, then implement 1.5.3–1.5.5.
2. **`FEATURE_RIGPA_LMS_ENABLED` removal from `docker-compose.yml` — RESOLVED (option 2).** Colossus grep confirmed no `.env.local` / systemd / shell rc / Caddy dependency on the var. In-repo references (`src/lib/feature-flags/flags.ts`, `index.ts`, `schemas/rigpa-lms.ts`, `tests/unit/feature-flags.test.ts`, ADR-003, ADR-004) intentionally kept — the flag stays alive in the frontend registry; only the dead compose declaration was removed. Operators toggle via `.env.local`.

## Exact next action
1. On Colossus: `cd ~/dev/forge-oh && git fetch origin && git checkout slice/stage1-reconciliation-v1 && git pull`
2. Regenerate `bff/requirements.lock` under Colossus's `.oh-venv` (Python 3.11+ actual): `.oh-venv/bin/pip-compile --strip-extras --no-annotate --output-file=bff/requirements.lock bff/requirements.txt`
3. `bash scripts/forge-restart.sh` then `bash scripts/forge-doctor.sh` — paste doctor output.
4. `pnpm install && pnpm typecheck && pnpm test:unit && pnpm build` from repo root.
5. Answer the ADR-009 question above so 1.5.3–1.5.5 can proceed.
