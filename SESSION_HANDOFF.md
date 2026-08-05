# Forge-OH Session Handoff — 2026-08-05 03:53 EDT

## Current build-sequencing position

- **Stage / phase:** F.19 (Path E rebench) → **DONE for planner**; Path F queued for coder
- **Slice branch:** `slice/coder-planner-rebench`
- **Blocked slice waiting to resume:** `slice/dual-mode-routing-impl` (git-stashed)

## Completed this session

- Model Council scoring pass (Claude Fable 5 + GPT 5.6 Sol + Gemini 3.1 Pro = 99 raw scores)
- Aggregated per-cell rankings; verified with three-scorer averaging
- **ADR-013 amended:** planner ratified · coder deferred to Path F
- **ADR-012 catalog seed** updated in-place (planner canonical flipped; coder retained as ADR-009 default per Path F deferral)
- **`bff/services/model_router.py`** — `LLM_PLANNER_MODEL` default flipped to `deepseek-r1-distill-32b-awq`; rollback env comment inline
- ADR index (`docs/adr/README.md`) row for ADR-013 updated to Amended status
- BUILD_LOG entry appended (2026-08-05 03:52 EDT)

## Ratified decision

- **Planner canonical:** `deepseek-r1-distill-32b-awq` (c12b) — vLLM `:8511`, AWQ-Marlin, `--reasoning-parser deepseek_r1`
- **Coder canonical:** `qwen3.6-35b-a3b-nvfp4` (ADR-009 default retained, provisional until Path F)

## Remaining before current Definition of Done

1. **Colossus operator step (blocking):**
   - `git pull origin slice/coder-planner-rebench`
   - Download DSR1-Distill-32B AWQ weights if not already present on Colossus (bench proved c12b runs; may already be cached)
   - Restart planner vLLM `:8511` with new default: `bash ops/vllm_supervisor.sh ensure planner` (or the equivalent restart script) — env var `LLM_PLANNER_MODEL` will now default correctly
   - Verify: `curl -s http://localhost:8511/v1/models` should list `deepseek-r1-distill-32b-awq`
2. **PORTING_LEDGER entry** for DSR1-Distill-32B AWQ (source URL, commit hash, SPDX license) — deferred until weights are pulled and verified on Colossus
3. **Resume `slice/dual-mode-routing-impl`** (`git stash pop`) with the ratified planner canonical

## Path F queued (coder-selection completion)

Scope for instrumented rebench + SWE-bench Verified:

- Extend `bench/pathE_qwen36_27b/bench_pathE.py` with NVML/nvidia-smi sampling loop:
  - Fields: `gpu_temp_avg_c`, `gpu_temp_max_c`, `gpu_util_avg_pct`, `gpu_util_max_pct`, `vram_avg_mib`, `vram_max_mib`
  - Sample every 500 ms during each request; roll up per response and per cell
- **Warm-up pass:** first request per (cell, task) is throw-away; scoring uses runs 2-4 (parity with gold-standard LLMs which run warm)
- **3× repetition** per (cell, task) → 4 total runs per pair; report min/med/max
- **Redesigned arch task:** remove or inline the importer-graph twist so the task is prompt-solvable
- **SWE-bench Verified** on top 2-3 coders (best expected model first for budget estimate)
- Author ADR-013 amendment #2 with the coder verdict when Path F concludes

## Open questions / awaiting user answer

- **None blocking.** Next action is operator-side: pull + restart planner vLLM.

## Exact next action

Operator on Colossus:

```bash
cd ~/dev/forge-oh
git pull origin slice/coder-planner-rebench
bash ops/vllm_supervisor.sh ensure planner
curl -s http://localhost:8511/v1/models | jq '.data[].id'
# Expect: "deepseek-r1-distill-32b-awq"
```

When that verifies, tell me and I'll spec + start Path F instrumentation work.
