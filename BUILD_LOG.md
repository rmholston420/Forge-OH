# Forge-OH — BUILD_LOG

Append-only build log per Kosmos custom instructions. Newest entries at the
bottom. Never edit or delete prior entries; supersede via a new dated entry.

Timestamp format: `YYYY-MM-DD HH:MM EDT`.

Related logs:
- `DEBUG_LOG.md` — append-only bug/error diagnoses (search FIRST before
  re-diagnosing).
- `SESSION_HANDOFF.md` — overwritten each session end, current state only.
- `PORTING_LEDGER.md` — vendored OSS ports (source URL, commit SHA, SPDX,
  modifications).

---

## 2026-08-02 21:30 EDT — Step 1 complete: real OpenHands agent-server on Colossus

**Stage / plugin / port:** Forge-OH-Action-Plan-v4 Step 1 — stand up real
OpenHands agent-server locally.

**What was built or changed:**
- Installed openhands-sdk / openhands-tools / openhands-agent-server /
  openhands-workspace at 1.40.0 into `.oh-venv` on Colossus. All four
  versions verified against PyPI (latest as of 2026-08-02).
- Booted `python -m openhands.agent_server --host 127.0.0.1 --port 8090`
  successfully. Server reports OpenHands SDK v1.40.0 in its banner.
- Captured full route table (103 paths) from
  `http://127.0.0.1:8090/openapi.json` and saved to
  `docs/agent-server-routes-1.40.0.txt`. Grouped by workflow for the
  vertical-slice backlog (conversation lifecycle, event stream,
  files/workspace, LLM config, tools/MCP/skills/plugins, secrets, bash,
  health).
- Verified end-to-end LLM loop against Ollama:
  `POST /api/conversations` + `POST /api/conversations/{id}/run` succeeded
  with `openai/qwen3.6:35b-a3b` at `http://localhost:11434/v1`.
  Result: `execution_status=finished`, `prompt_tokens=8163`,
  `completion_tokens=2775`, 9 events. Plan Step 1 stop condition met.
- Bumped `.env.example`: SDK `1.29.3` → `1.40.0`; removed obsolete
  "runtime image tag: 0.60.0" reference (V1 has no separate runtime image);
  added Ollama config vars (`OLLAMA_BASE_URL`, `OLLAMA_PRIMARY_MODEL`,
  `OLLAMA_FAST_MODEL`, `OLLAMA_ALT_MODEL`); removed `SECRET_KEY`,
  `TOKEN_TTL_HOURS`, `FEATURE_RIGPA_LMS_ENABLED` (Step 2 will delete their
  code).
- Updated `bff/services/model_router.py` defaults for the Colossus stack:
  `PRIMARY_MODEL=qwen3.6:35b-a3b`, `FAST_MODEL=qwen3-coder:30b`, added
  `ALT_MODEL=qwen3.6:27b`, added `OLLAMA_BASE_URL` constant, renamed
  `DEVSTRAL_CTX_LIMIT` → `PRIMARY_CTX_LIMIT` (env-configurable), added
  `"alt"` branch to `route_request()`. All public names from the previous
  version preserved (`OLLAMA_URL`, `VLLM_URL`, `PRIMARY_MODEL`,
  `FAST_MODEL`, `ollama_health_check`, `vllm_health_check`, `route_request`,
  `ModelUnavailableError`, `try_model`, `VLLM_FALLBACK_MODEL`) —
  `bff/routers/settings.py` import block unaffected.
- Pulled Ollama models on Colossus: `qwen3.6:35b-a3b` (23 GB, primary),
  `qwen3-coder:30b` (18 GB, fast — shares digest `06c1097efce0` with
  the previously-pulled `qwen3-coder:latest`).

**Files touched:**
- `.env.example` (rewritten)
- `bff/services/model_router.py` (updated)
- `docs/agent-server-routes-1.40.0.txt` (new)
- `BUILD_LOG.md` (created — this file)

**Ports/adapters affected:** none (Step 1 is spec + config only; no BFF
routers wired yet).

**ADR or ledger updated:** none. `PORTING_LEDGER.md` not created yet —
first port lands in a later step.

**Stop-condition status:** Step 1 stop condition met. Next slice = Step 2
(strip auth/RBAC/LMS) before Step 3 vertical slice.

**Notes / deferred:**
- Agent-server default config points at `host.docker.internal:11434` and
  `openai/devstral-small-2:24b`. Not a problem: Forge-OH will supply
  the full LLM config on every `POST /api/conversations` call. The
  server-side default is only fallback.
- `tmux` installed on Colossus to silence the agent-server warning.
- LiteLLM cost-calc warning for `qwen3.6:35b-a3b` (not in the price DB)
  is cosmetic; ignore.
- OpenHands agent-server also exposes `POST /v1/chat/completions` and
  `GET /v1/models` (its own OpenAI-compatible endpoint). Not used yet;
  distinct from Ollama's `/v1`.

## 2026-08-02 21:55 EDT — Step 2 executed: auth/RBAC/LMS strip (expanded scope)
- **Stage:** Forge-OH Action Plan v4 Step 2 — remove auth/RBAC/LMS scaffolding to unblock stub-replacement work
- **Scope confirmed by user before execution:** delete backend auth+rbac+lms, delete frontend auth+rigpa-lms, strip AuthGuard/CanDo/RoleChip wrappers from all feature files, prune coupled tests

### Backend deletions
- `bff/middleware/rbac.py`, `bff/routers/auth.py`, `bff/routers/lms.py`, `bff/auth_state.py`
- Tests coupled to `auth_state._TOKENS` or `/api/auth/demo-login` (rewrite in Step 3+):
  - `bff/tests/test_rbac.py`, `test_auth.py`, `test_auth_router.py`, `test_lms.py`, `test_lms_router.py`
  - `bff/tests/test_runs_router.py`, `test_workspaces_router.py`, `test_secrets.py`
  - `bff/tests/test_agent_presets_router.py`, `test_secrets_router.py`

### Backend edits
- `bff/main.py` — removed `auth` and `lms` router imports+includes; updated docstring
- `bff/settings.py` — dropped `secret_key`, `token_ttl_hours`, `feature_rigpa_lms_enabled`
- `bff/tests/utils.py` — removed `auth`+`lms` from multi-router test app
- `bff/routers/{runs,workspaces,mcp,plugins,agent_presets}.py` — stripped every `Depends(require_role(...))` parameter and `bff.middleware.rbac` import; also removed now-unused `Depends` import
- `bff/routers/secrets.py` — removed `bff.auth_state._TOKENS` import; neutralised `if token not in _TOKENS` guard to `pass` (endpoints still callable; real auth returns in later stage)
- `bff/Dockerfile` — updated `--workers 1` comment (no longer references deleted `_TOKENS`)

### Frontend deletions (folders)
- `src/components/auth/` (AuthGuard, CanDo, RoleChip)
- `src/app/(auth)/` (login page), `src/app/api/auth/` (NextAuth catch-all)
- `src/features/rigpa-lms/`
- `src/lib/auth/`, `src/lib/rbac/`, `src/lib/schemas/auth.ts`, `src/types/next-auth.d.ts`

### Frontend deletions (unit tests)
- `src/tests/unit/rbac-permissions.test.ts`, `rbac-withPermission.test.tsx`
- `src/tests/unit/auth-RoleChip.test.tsx`, `auth-schemas.test.ts`, `auth-schemas-edge-cases.test.ts`
- `src/tests/unit/LoginPage.test.tsx`, `AuthGuard.test.tsx`, `CanDo.test.tsx`, `usePermissions.test.ts`
- `src/tests/unit/rigpa-lms-schemas.test.ts`, `rigpa-lms-store.test.ts`, `schemas.test.ts` (LMS-only)

### Frontend edits
- `src/app/providers.tsx` — dropped `SessionProvider` (NextAuth removed)
- `src/lib/http/bff-client.ts` — dropped `getSession()` Bearer-token injection; default BFF port fixed to 8081
- `src/app/(dashboard)/layout.tsx` — removed top-level `<AuthGuard>` wrapper
- Feature files (10) — removed `<CanDo permission=...>` wrappers, kept children inline; removed `CanDo`/`Permission` imports:
  - `plugins/PluginsPage.tsx`
  - `mcp/McpPage.tsx`, `mcp/McpServerCard.tsx`
  - `workspaces/WorkspaceCard.tsx`, `workspaces/WorkspacesPage.tsx`
  - `secrets/SecretsPage.tsx`, `secrets/SecretRow.tsx`
  - `agent-presets/AgentPresetsPage.tsx`, `agent-presets/AgentPresetCard.tsx`
- `src/tests/mocks/handlers.ts` — removed `/api/lms/*` handlers and rigpa-lms fixtures import

### Ports/adapters affected
- Backend routers still expose same paths; RBAC layer removed → all endpoints are now open (single-user local dev per project instructions)
- BFF client no longer sends `Authorization: Bearer` header (BFF ignores it anyway)

### Verification
- `python3 -m compileall bff/` → clean
- Sweep for residuals (`auth_state`, `_TOKENS`, `require_role`, `middleware.rbac`, `next-auth`, `useRequireAuth`, `<AuthGuard>`, `<CanDo>`, `<RoleChip>`, imports from `@/lib/auth`, `@/lib/rbac`, `@/lib/schemas/auth`, `@/components/auth`, `@/features/rigpa-lms`) → **zero residuals** across `bff/` and `src/` (production code and tests)

### Stop condition
- Step 2 DoD (per Forge-OH-Action-Plan-v4 lines 100-104): dev server + BFF must boot without `auth`/`lms` routers. Sandbox cannot verify (no `socketio` / node deps installed). **User must run `git pull` on Colossus, then `cd bff && uvicorn bff.main:app_with_sio --port 8081` and `pnpm dev` in repo root to confirm.**

### Deferred to Step 3
- `bff/openhands_client.py` duplicate (canonical) vs `bff/services/openhands_client.py` (shim) — resolve during runs-router rewrite
- Stub `POST /api/runs` still returns hardcoded run — Step 3 wires it to real conversation lifecycle
- Fresh router tests for `runs`, `workspaces`, `secrets`, `agent_presets` — write against real behaviour, not seeded tokens


## 2026-08-02 21:47 EDT — requirements.txt aligned to openhands 1.40.0
- **Symptom:** `uvicorn bff.main:app_with_sio` fails with `ModuleNotFoundError: No module named 'socketio'` in `.oh-venv` (which only has openhands 1.40.0)
- **Cause:** `bff/requirements.txt` and root `requirements.txt` both still pinned `openhands-sdk==1.29.3`; BFF deps (fastapi, python-socketio, aiosqlite, httpx) never installed into `.oh-venv`
- **Fix:**
  - Bumped both files to `openhands-sdk/tools/agent-server/workspace==1.40.0`
  - Removed `python-jose`+`passlib` from `bff/requirements.txt` (auth stripped in Step 2)
- **Files touched:** `bff/requirements.txt`, `requirements.txt`
- **Next:** user runs `pip install -r bff/requirements.txt` inside `.oh-venv`, then retries uvicorn

