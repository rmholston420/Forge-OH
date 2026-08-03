# Forge-OH — Session Handoff

Overwrite this file at the end of every session. Reflects current state only.

---

## Current stage
**F.19-pre COMPLETE (ADR-009 accepted, amended with topology + budgets).**

Decisions locked in this session:
- **Coder:** `qwen3.5-nvfp4` on vLLM, `max_tokens=2048`.
- **Planner:** `qwen3-thinking-2507-awq` on vLLM, `max_tokens=8192`.
- **Topology:** dual-port (`:8501` coder, `:8502` planner) + swap-on-demand
  supervisor at `ops/vllm_supervisor.sh` (F.19 scope).
- **BFF port:** stays on `:8081`. `colossus-ops` skill will be corrected
  in a separate pass.

Two forks going forward:
- **F.19** — router wiring against c08 as planner. Not blocked.
- **F.19-pre-b** — re-bench c05/c06/c07 on P3 only at `max_tokens=8192`.
  If c05 or c06 outscores c08 (23 on P3) AND is materially faster, a
  superseding ADR promotes it. Runs in parallel with F.19.

## Ambient
- vLLM: RUNNING at `:8500` serving F.18's `qwen3-coder-30b` GGUF
  (unchanged until F.19 rewires to `:8501/:8502`).
- Ollama: STOPPED + systemd `disabled`.
- Agent-server: RUNNING at `:8090`.
- BFF: RUNNING at `:8081` (F.18c dotenv fix in place).
- Frontend: RUNNING at `:3000`.
- Bench weights (`qwen3.5-nvfp4`, `qwen3-thinking-2507-awq`) already on
  disk in `~/.cache/huggingface/hub/`.
- GPU free: ~3.1 GB / 32 GB (all held by the F.18 vLLM process).

## What was completed this session
1. F.19-pre 8-cell bench (24 answers).
2. All 24 answers scored across 4 dimensions —
   `bench/f19pre/results/scores_20260803.md`.
3. **ADR-009 authored and amended** with:
   - Coder + planner picks
   - Dual-port + supervisor topology
   - Token budgets (coder 2048, planner 8192)
   - F.19-pre-b re-bench as an explicit follow-up
4. BUILD_LOG appended.
5. Pushed to `main` — commits `4cb2a09` (initial ADR) and this one.

## What remains before Definition of Done for F.19
1. **Launcher rework** (F.19.1):
   - `ops/vllm_launch_coder.sh` — starts `qwen3.5-nvfp4` on `:8501`,
     `--max-num-seqs 128 --gpu-memory-utilization 0.90`, no explicit
     `--quantization` (autodetect compressed-tensors).
   - `ops/vllm_launch_planner.sh` — starts `qwen3-thinking-2507-awq`
     on `:8502`, same VRAM flags.
   - `ops/vllm_supervisor.sh` — accepts `coder|planner`, stops the
     other, waits for `/v1/models` readiness on the target port.
2. **Router rework** (F.19.2 — `bff/services/model_router.py`):
   - New env vars: `LLM_CODER_URL=http://localhost:8501/v1`,
     `LLM_CODER_MODEL=qwen3.5-nvfp4`,
     `LLM_PLANNER_URL=http://localhost:8502/v1`,
     `LLM_PLANNER_MODEL=qwen3-thinking-2507-awq`,
     `LLM_CODER_MAX_TOKENS=2048`, `LLM_PLANNER_MAX_TOKENS=8192`.
   - Router selects `coder` vs `planner` by request `role` (or a
     heuristic if role is absent — F.19.2 decision, likely default to
     coder).
   - Router calls the supervisor before dispatching if the target
     port's `/v1/models` probe fails.
3. **Tests** (F.19.3): mirror F.18b's
   `bff/tests/test_model_router.py` — cases for role dispatch, health
   probe, supervisor-triggered swap, fallback to Ollama when both
   vLLM launchers are down.
4. **Live smoke** (F.19.4): run F.19-pre's P1/P2/P3 through the
   rewired router and confirm the answers still hit c04/c08 quality.
5. **F.19-pre-b** (parallel): three-cell re-bench, planner P3 only,
   `max_tokens=8192`. Score. Amend ADR-009 or supersede.

## Open questions / ambiguity
None blocking. All F.19-pre open items were resolved this session.

Latent concern (not blocking F.19):
- **Swap cost quantification.** ADR-009 assumes role transitions are
  infrequent enough that swap cost (~30-60s weight reload) is
  acceptable. If real usage shows frequent coder↔planner interleaving,
  F.19 may need a second ADR on either (a) a smaller planner model
  co-resident with the coder, or (b) a preemption policy. Measure
  after F.19 is live.

## Exact next action
Read `bff/services/model_router.py` to inventory current routes and
health-check surfaces:

```bash
cd ~/dev/forge-oh
grep -n 'route_request\|health_check\|VLLM_\|OLLAMA_\|def [a-z]' bff/services/model_router.py | head -40
grep -n 'MODEL_ROUTE\|BACKEND\|coder\|planner\|role' bff/services/model_router.py | head -40
```

Then draft F.19.1 (launcher scripts) as the first commit.

## Key files/refs
- **ADR-009:** `docs/adr/009-local-llm-selection.md`
- **Scores:** `bench/f19pre/results/scores_20260803.md`
- **Packed answers:** `bench/f19pre/results/bench_f19pre_20260803_175759.md`
- **Raw JSON:** `bench/f19pre/results/raw/20260803_170129_run/`
- **F.19-pre launchers (reference):** `bench/f19pre/vllm_launch.sh`
- **Commits this session:** `4cb2a09` (ADR-009 + scores + logs), plus
  the amendment commit that follows this handoff overwrite.
