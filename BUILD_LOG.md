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
