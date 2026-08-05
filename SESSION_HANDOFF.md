# Forge-OH Session Handoff — 2026-08-05 04:55 EDT

## Current build-sequencing position

- **Stage / phase:** F.3 (LiveCodeBench-v6 validation of ratified coder)
- **Plugin / kernel component:** bench/pathF_instrumented → LiveCodeBench-v6 runner
- **Port(s) in progress:** LiveCodeBench-v6 harness (upstream `LiveCodeBench/LiveCodeBench`, Apache-2.0). Weights already local: `qwen3.6-27b-int4-autoround` (c01, ratified coder).

## Completed this session

- F.1a NVML smoke test on c11 — instrumentation validated, no VRAM conflict once planner torn down (serial VRAM policy locked in).
- F.1b full instrumented rebench (c11 Devstral-24B AWQ + c03b Qwen3-Coder-30B MoE AWQ + c01 Qwen3.6-27B INT4 AutoRound) — 3 cells × 3 prompts × (1 warmup + 3 scored runs) with 500ms NVML sampling of VRAM/util/temp/power. All completed 04:32–04:39 EDT.
- F.2 arch_v2 gold generation — new `bench/prompts/arch_v2_router.txt` (router-design task, solvable from prompt alone) with 3-Council gold + Opus 5 synthesis at `/home/user/workspace/gold-arch_v2-council-synthesis.md`. Council converged on hysteresis + latency-gate + coder-safe-default with 7-level predicate.
- F.1b Council scoring pass — 3 scorers ranked `c01 > c11 > c03b` unanimously (112.7 > 101.0 > 73.0 /200 combined avg). 11.7-point margin over 2nd and 39.7-point margin over 3rd, both well beyond the 3-point ADR tie window.
- **ADR-013 amendment #1 filed** ratifying c01 (Qwen3.6-27B INT4 AutoRound) as canonical coder. `LLM_CODER_MODEL` env default flipped in `bff/services/model_router.py`. `ops/vllm_launch_coder.sh` defaults + flags updated (`--tool-call-parser qwen3_coder`, `--enable-auto-tool-choice`; removed `--quantization modelopt_fp4` — compressed-tensors auto-detected). Rollback path documented inline.
- `docs/adr/README.md`, `PORTING_LEDGER.md`, `BUILD_LOG.md`, `SESSION_HANDOFF.md` all updated.

## Remaining before current Definition of Done

Coder ratification (this slice) is done. Next slice is F.3 LiveCodeBench-v6 validation on c01:

1. Load `bench/pathF_instrumented/` harness pattern for LiveCodeBench-v6.
2. Vendor LiveCodeBench-v6 loader (Apache-2.0 — permissive, permitted per Forge-OH porting skill). Log in `PORTING_LEDGER.md`.
3. Latest-window filter: problems dated Jan 2026 – Aug 2026 (~150 problems, contamination-filtered against Qwen3.6/DSR1/Codestral/Devstral training cutoffs).
4. **First-model dry run on c01** to establish per-problem latency (needed for time-budget estimate before running the full 3-model matrix in F.4).
5. Metric: pass@1 with the standard LiveCodeBench evaluator.
6. F.4 = 3-model matrix (c01 + c11 + c03b) IF F.3 dry run comes in under ~2 hours per model; otherwise winner-only run at F.5.
7. F.5 = SWE-bench Verified on c01 (Tier 2, overnight run).
8. **ADR-013 amendment #2** if LiveCodeBench/SWE-bench confirm F.1b verdict (or supersede it if they disagree).

## Open questions / awaiting user answer

- **VRAM policy for F.3+:** still serial (tear down planner during coder-only bench)? LiveCodeBench-v6 is coder-only, same as F.1b, so serial is the assumed default. Confirm before F.3 dry run.
- **F.3 model matrix scope:** run c01 only for time estimate first, then decide whether F.4 matrix is worth the token budget vs. skipping straight to F.5 SWE-bench on c01. (Default = run c01 first, decide after.)

## Exact next action

**Operator step 1** — activate ratified coder on Colossus:

```bash
cd ~/dev/forge-oh
git pull

# Confirm planner is still down (it was torn down for F.1b, not restored)
docker ps --filter name=forge-vllm

# Bring up ratified coder (c01) via the updated launcher
docker rm -f forge-vllm-coder 2>/dev/null || true
bash ops/vllm_supervisor.sh ensure coder

# Verify: should serve as "qwen3.6-27b-int4-autoround"
curl -s http://localhost:8501/v1/models | jq '.data[].id'

# Bring planner back up
bash ops/vllm_supervisor.sh ensure planner
curl -s http://localhost:8511/v1/models | jq '.data[].id'
```

**Operator step 2** — smoke test via BFF (verify LLM_CODER_MODEL env default picked up):

```bash
cd ~/dev/forge-oh
bash scripts/forge-restart.sh --bff-only
bash scripts/forge-status.sh
# BFF should now default-route coder to qwen3.6-27b-int4-autoround
```

**Then:** agent will pick up F.3 (LiveCodeBench-v6 vendoring + c01 dry run) on next resume.
