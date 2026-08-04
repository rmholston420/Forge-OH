# SESSION_HANDOFF — 2026-08-04 02:03 EDT

## Current stage / component
Post-G.1 hardening. G.1 merged to main (`d36e72a`). Slice
`vllm-supervisor-gpu-discipline` in flight; pending push + merge.
Forge-OH-Action-Plan-v4 has no formal stage number for this work —
treat it as an F.19-post hotfix.

## What was completed this session
1. G.1 self-eval harness landed and merged to main (see prior session
   handoff — cycle `smoke-add-two`, `smoke-reverse-string`,
   `smoke-json-roundtrip` all passed on Ollama fallback
   `qwen3-coder:32k`).
2. Post-merge, tried to bring the vLLM coder back up per ADR-009
   (c04 primary). Container crashed with
   `Free memory on device cuda:0 (24.85/31.39 GiB) on startup is
   less than desired GPU memory utilization`.
3. Verified crash was GPU contention (Ollama holding VRAM), NOT a
   vLLM version or quant-flag bug. `vllm/vllm-openai:latest`
   (currently `0.26.0`) is the correct image per ADR-009 §5 and
   Follow-up 4.
4. Manually stopped Ollama, launched c04 with 31.4 GiB free →
   `/v1/models` returned `qwen3.6-35b-nvfp4`, inference smoke
   returned in 21.3 s. c04 operational.
5. Patched `ops/vllm_supervisor.sh` with GPU-tenancy discipline
   (`_stop_ollama`, `_free_gpu_for_vllm`, `cmd_up` integration,
   new `check` subcommand, library-mode guard).
6. Wrote `ops/test_supervisor.sh` (14 offline tests, all
   pass locally on the audit checkout).
7. Amended ADR-009 with Follow-up 5 documenting the discipline
   landing.
8. Appended BUILD_LOG (2026-08-04 02:03 EDT) and DEBUG_LOG
   (2026-08-04 02:03 EDT).

## What remains before Definition of Done
- Commit the slice branch on the audit checkout and push to origin.
- Merge `slice/vllm-supervisor-gpu-discipline` into `main` on GitHub.
- Delete the slice branch.
- On Colossus: `git pull origin main` in `~/dev/forge-oh` so the
  patched supervisor is active before the next `up coder` /
  `up planner` cycle.
- Optional verification: run `ops/test_supervisor.sh` on
  Colossus and run `ops/vllm_supervisor.sh check` while c04 is up
  (expect `SHORT` because vLLM is holding ~28 GB — that's correct).

## Open questions / ambiguity
None. Discipline design and threshold values (28000 MiB / 30 s / 0.9
GPU util) are directly derived from ADR-009 §5 and the crash log
(free < 28.25 GiB).

## Exact next action
1. In `/home/user/workspace/audit/forge-oh`:
   ```
   git add ops/vllm_supervisor.sh ops/test_supervisor.sh \
           docs/adr/009-local-llm-selection.md \
           BUILD_LOG.md DEBUG_LOG.md SESSION_HANDOFF.md
   git -c user.name="Perplexity Computer" \
       -c user.email="computer@perplexity.ai" \
       commit -m "supervisor: enforce GPU-tenancy discipline (stop Ollama + verify memory.free before vLLM launch); ADR-009 §5 Follow-up 5"
   git push origin slice/vllm-supervisor-gpu-discipline
   ```
2. Open + squash-merge PR into main via `gh` (Perplexity Computer
   identity), delete the slice branch.
3. On Colossus: `cd ~/dev/forge-oh && git pull origin main`.
4. Verify with `ops/test_supervisor.sh` on Colossus.

## State of Colossus at session close
- `forge-vllm-coder` container: `Up 3+ minutes` on `:8501`
  (VRAM 28.3 GB used / 3.8 GB free).
- Ollama systemd: stopped (as of manual launch step).
- BFF `:8081`: last started with `LLM_CODER_OLLAMA_FALLBACK=qwen3-coder:32k
  VLLM_SUPERVISOR_ENABLED=0`. After the next `git pull` and BFF
  restart, `LLM_CODER_OLLAMA_FALLBACK=qwen3-coder:32k` is the code
  default (merged in G.1) so the env override is no longer required.
- Router routing to vLLM `:8501` should work on the next request
  (cache miss → `_supervisor_ensure coder` → `check` sees `:8501`
  is live → no-op).

## Push credentials
`api_credentials=["github"]` — commit as
`Perplexity Computer <computer@perplexity.ai>`.
