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

---

## 2026-08-05 — c01 context-budget-skip ceiling at `max_model_len=32768` (INFORMATIONAL)

- **Blocks:** none. Informational ceiling documenting an honest limit of c01's context window.
- **Symptom:** 35/500 tasks (7.0%) in F.3 full-500 skipped by harness with `ERROR: context-budget-skip: prompt_tokens=N leaves only Xt room (< floor 512)`. All skipped tasks had oracle-file `prompt_tokens > 32k` (matplotlib, sympy, xarray dominant repos). Harness correctly counts these against pass@1 as unresolved-with-error (conservative). Raw pass@1 = 0.266 / attempted-only pass@1 = 0.286 — the 2pt spread reflects the ceiling.
- **Smoke-30 v2 skip rate:** 4/30 tasks (13.3%) skipped in `20260805_2106_run` — **intentionally over-sampled vs the 7.0% full-500 base rate.** The smoke's 30-task budget quantizes small proportions harshly; sampling proportionally would have yielded 2 skips (6.7%), but 4 was chosen to reliably exercise the context-budget-skip code path on every regression run. This is a smoke-design property, not a signal that skip rate is rising. The skipped tasks in smoke-30 v2 are: `django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248` — all confirmed skips in the full-500 ground truth.
- **Root cause:** c01 (`c01_coder_vllm_qwen36_27b_int4`) launched with `--max-model-len 32768`. Oracle-retrieval loads full ground-truth file contents; matplotlib `axes/_axes.py`, sympy multi-file oracle sets, xarray large modules exceed 32k tokens at 4k output reserve. Model itself (Qwen3.6-27B) supports 128k context natively.
- **Attempted fixes:** none — this is an informational entry, not a bug. F.3 was deliberately kept at 32k `max_model_len` per launcher config.
- **Next investigation:** if Stage 2+ requires raising `max_model_len`, factor in VRAM budget (F.3 already saturated at 99.98% / 32,599 MiB peak). Options: (a) raise `max_model_len` to 65536 or 131072 with `kv-cache-dtype=fp8` retention and reduced `max-num-seqs`, (b) implement oracle-file compression (modified-regions-plus-context) in `oracle_prompt.py`, (c) accept as honest capability ceiling. Path B (Stage 1H.5 agent loop with iterative test-run-fix) may be higher-leverage than raising context alone.
- **Related DEBUG_LOG search terms:** `context-budget-skip`, `max-model-len`, `oracle_prompt`, `prompt_tokens exceeds`, `KV cache VRAM`, `smoke-30`, `smoke skip rate`.
