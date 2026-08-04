# SESSION_HANDOFF — 2026-08-04 02:24 EDT

## Current stage / component
Post-G.1 hardening. G.1 merged to main (`d36e72a`). Supervisor
GPU-tenancy discipline merged to main (`117e263`). Slice
`vllm-primary-selfeval-verification` in flight; code changes complete
locally, Colossus verification pending. Forge-OH-Action-Plan-v4 has no
formal stage number for this work — treat it as an F.19-post hotfix
sequence.

## Correction to previous handoff

The previous handoff (and the pre-compaction summary that seeded it)
claimed the G.1 slice landed a code-default change from
`qwen3-coder:30b` to `qwen3-coder:32k` in `bff/services/model_router.py`.
**That claim was false.** Git history confirms: `d36e72a` (the G.1
merge) does not touch line 107 of `model_router.py`; the default
remained `qwen3-coder:30b`. The green G.1 cycle passed only because
the operator had `LLM_CODER_OLLAMA_FALLBACK=qwen3-coder:32k` exported
in the shell that started the BFF. The code-default change is being
landed correctly in the current slice.

## What was completed this session

**Prior slices (already merged to main):**
1. G.1 self-eval harness (`d36e72a`). Cycle passed on Ollama
   fallback via shell env override `qwen3-coder:32k`.
2. Supervisor GPU-tenancy discipline (`117e263`, PR #1). 14/14
   offline tests pass on audit checkout AND Colossus. Manual c04
   launch clean.

**Current slice (`slice/vllm-primary-selfeval-verification`, not
yet merged):**
3. `bff/services/model_router.py` line 106-114: code default for
   `LLM_CODER_OLLAMA_FALLBACK` changed from `qwen3-coder:30b`
   → `qwen3-coder:32k`. Comment added referencing ADR-009 §2 and
   the num_ctx rationale.
4. `bff/tests/test_model_router.py`: two new regression tests
   (`test_coder_ollama_fallback_defaults_to_32k`,
   `test_coder_ollama_fallback_env_override_wins`). All 18 tests
   in the file pass locally.
5. SESSION_HANDOFF corrected (this file).

## What remains before Definition of Done
1. Commit the slice branch, push, PR, squash-merge to main, delete
   branch.
2. On Colossus: `git pull origin main`, restart BFF pointed at vLLM
   primary (`VLLM_SUPERVISOR_ENABLED=1`, no `LLM_CODER_OLLAMA_FALLBACK`
   override).
3. Run one full smoke cycle (`smoke-add-two`,
   `smoke-reverse-string`, `smoke-json-roundtrip`).
4. Verify every trajectory shows model tag `qwen3.6-35b-nvfp4`
   (i.e. c04), NOT `qwen3-coder:32k`.
5. Confirm Ollama systemd stayed stopped throughout (supervisor
   holds GPU tenancy discipline).

## Open questions / ambiguity
None open for this slice. Next slice after this one is the
ADR-0001 amendment (ollama-first → vllm-primary supersession).

## Exact next action
1. Commit + push slice branch, PR, squash-merge to main.
2. On Colossus, restart BFF with `VLLM_SUPERVISOR_ENABLED=1` and
   run the smoke cycle (paste block supplied in-session).
3. Verify c04 routing via trajectory inspection.
4. Log green cycle in BUILD_LOG.

## State of Colossus at session close
- `forge-vllm-coder` container: `Up ~20 minutes` on `:8501`
  (VRAM ~28 GB used).
- Ollama systemd: stopped.
- BFF `:8081`: last started with `LLM_CODER_OLLAMA_FALLBACK=qwen3-coder:32k
  VLLM_SUPERVISOR_ENABLED=0`. After this slice merges + Colossus
  pulls main:
  - `LLM_CODER_OLLAMA_FALLBACK` env override no longer required
    (code default is now `qwen3-coder:32k`).
  - `VLLM_SUPERVISOR_ENABLED=1` MUST be set for vLLM-primary routing.
- Router should route to vLLM `:8501` on the next request
  (cache miss → `_supervisor_ensure coder` → sees `:8501` live →
  no-op).

## Push credentials
`api_credentials=["github"]` — commit as
`Perplexity Computer <computer@perplexity.ai>`.
