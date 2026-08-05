# Forge-OH — KNOWN_ISSUES

Open, unresolved issues that do not block current-stage progress. Each entry
names the blocker scope, the affected stage/plugin/port, and the plan for
resolution. When resolved, move the entry into DEBUG_LOG.md as a closed
diagnosis (with fix) and delete from here.

Timestamp format: `YYYY-MM-DD HH:MM EDT`.

---

## 2026-08-05 — Agent-preset `ModelId` is a static Literal, no local endpoints wired

- **Blocks:** none at Stage 1. Blocks Stage 2 (Inference-Backend Flexibility) exit-gate acceptance.
- **Symptom:** `bff/routers/agent_presets.py` declares `ModelId = Literal["gpt-4o", "claude-opus-4", "gemini-2.5-pro", "local-llama"]`. There is no mapping from any of these literals to actual endpoints (`http://127.0.0.1:8501/v1` coder vLLM, `http://127.0.0.1:8511/v1` planner vLLM, `http://127.0.0.1:11434/v1` Ollama). Seed presets `ap-1` (gpt-4o, default) and `ap-2` (claude-opus-4) both point at cloud LLMs. No preset for the canonical Colossus stack exists, and there is no way to create one that resolves to a local endpoint through the current preset schema.
- **Root cause:** Stage 1 wired the preset CRUD surface (POST/GET/PUT/DELETE against a real store) but did not add an `InferenceBackend` protocol that maps `ModelId` → `{endpoint, api_style, sampling_defaults}`. This is Stage 2 scope per `docs/reconciliation-plan-v1.md`.
- **Attempted fixes:** none. Deferred by design — Stage 2.1 is exactly the "InferenceBackend protocol in `model_router.py`" work.
- **Next investigation:** Stage 2.1 kickoff. See `docs/reconciliation-plan-v1.md` Stage 2 sub-slice 2.1.
- **Related DEBUG_LOG search terms:** `ModelId`, `local-llama`, `InferenceBackend`, `preset local endpoint`, `agentPresetId null`.

---

## 2026-08-05 — `GET /api/runs/{id}` returns `agentPresetId: null` on succeeded runs

- **Blocks:** none at Stage 1. Blocks Stage 2 exit-gate item "creating a preset with a real local model … produces a `routing.model` matching that preset."
- **Symptom:** `curl /api/runs/6bad3048-5dcb-474b-8e32-fcdadb849cf6 | jq '.data.agentPresetId'` returns `null` even though the run completed successfully via a Colossus vLLM endpoint. `selectedModel` is populated (`openai/qwen3.6-35b-nvfp4`) but the preset FK is not persisted on the run record.
- **Root cause:** unconfirmed. Two hypotheses:
  1. The run creation path (`bff/routers/runs.py`) does not pass `agentPresetId` through to the run store when the request omits it, and the historical successful runs pre-date the requirement.
  2. The run store's write path drops the field, or the read path shape omits it.
- **Attempted fixes:** none. Read-path inspection only.
- **Next investigation:** paired with the ModelId issue above; both resolve together in Stage 2.1 when the router formally consumes preset config.
- **Related DEBUG_LOG search terms:** `agentPresetId null`, `run detail preset`, `run store write`.

---

## 2026-08-05 — pnpm workspace CI check fails on every PR (Node 20 + workspace config)

- **Blocks:** none. `mergeable: true` on all merged PRs (#5, #6, #7, closeout).
- **Symptom:** GitHub Actions `pnpm store path --silent` step exits non-zero with `packages field missing or empty`. Every push to `main` shows 2 red checks including check runs against `main` itself.
- **Root cause:** pnpm v11 + Node 20 deprecation interaction with the workspace configuration. Not code-related; the failure is in the CI action's pre-flight step, before any repo command runs.
- **Attempted fixes:** none. Discovered during PR #5-#7 merges.
- **Next investigation:** pin pnpm setup-action version, or set explicit `packages` field in `pnpm-workspace.yaml` if one exists, or migrate the CI check to a different step order that survives the pnpm store bootstrap.
- **Related DEBUG_LOG search terms:** `pnpm store path`, `packages field missing`, `pnpm-lock`, `CI red`.
