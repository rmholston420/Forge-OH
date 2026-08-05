# Path F — Instrumented Coder Rebench

Extends Path E with NVML instrumentation (GPU util, VRAM, temp, power)
so the ADR-013 coder rebench captures the hardware envelope, not just
quality + speed.

## Contents

| File | Purpose |
|---|---|
| `nvml_sampler.py` | pynvml background sampler; 500ms cadence; util/vram/temp/power |
| `bench_pathF.py` | Path E harness + sampler wired around every request |
| `README.md` | this file |

## Prerequisites (on Colossus, once)

```bash
cd ~/dev/forge-oh
source .oh-venv/bin/activate
pip install pynvml
python -m bench.pathF_instrumented.nvml_sampler   # 5s smoke test → JSON stats
```

Expected smoke-test output (~5s):
```
NVML available: True
sampling for 5s...
{
  "samples": 10,
  ...
  "gpu_util_avg_pct": 3.5,
  "vram_avg_mib": 727.0,
  "gpu_temp_avg_c": 41.0,
  "power_avg_w": 33.4
  ...
}
```

If `NVML available: False`, `pynvml` did not install correctly. Check
`pip list | grep -i nvml` and reinstall.

## F.1a — Instrumentation smoke test (5-min run)

Launch a single vLLM coder (c11 = Devstral-24B AWQ), then:

```bash
cd ~/dev/forge-oh
source .oh-venv/bin/activate

# 1) Launch c11
bash bench/pathE_qwen36_27b/vllm_launch.sh c11
curl -s http://localhost:8000/v1/models | jq '.data[].id'
# Expect: "c11_coder_vllm_devstral24b_awq"

# 2) Smoke run — 1 prompt x 1 run x 1 cell, no warmup
python -m bench.pathF_instrumented.bench_pathF --cells c11 --smoke

# 3) Inspect one JSON
ls ~/.forge-oh/bench_pathF/*_run/
cat ~/.forge-oh/bench_pathF/*_run/c11__debug.json | jq '.gpu_aggregate, .tokens_per_s_med, .completion_tokens'
```

Success criteria:
- Smoke run completes in <2 min.
- `gpu_aggregate.samples_total > 0`.
- `vram_max_mib` >20000 MiB (Devstral loaded, actively serving).
- `gpu_util_max_pct` >50% during generation.
- No errors in the JSON.

## F.1b — Full shortlist rebench

Once F.1a passes, run the ADR-013 top-3 shortlist:

```bash
cd ~/dev/forge-oh
source .oh-venv/bin/activate

# Order: c11 first (already running from F.1a), then c03b, then c01
# Between cells, relaunch vLLM with the target cell's model.

# c11 — already running from F.1a
python -m bench.pathF_instrumented.bench_pathF --cells c11

# c03b — Qwen3-Coder-30B AWQ MoE
bash bench/pathE_qwen36_27b/vllm_down.sh
bash bench/pathE_qwen36_27b/vllm_launch.sh c03b
curl -s http://localhost:8000/v1/models | jq '.data[].id'
python -m bench.pathF_instrumented.bench_pathF --cells c03b

# c01 — Qwen3.6-27B INT4
bash bench/pathE_qwen36_27b/vllm_down.sh
bash bench/pathE_qwen36_27b/vllm_launch.sh c01
curl -s http://localhost:8000/v1/models | jq '.data[].id'
python -m bench.pathF_instrumented.bench_pathF --cells c01
```

Or (equivalent shortcut) with the manual container swap between cells:

```bash
python -m bench.pathF_instrumented.bench_pathF --cells shortlist
# → runs c11, c03b, c01 in order (assumes you relaunch vLLM between them)
```

**Note:** the harness does NOT auto-launch vLLM cells — same as Path E,
the operator is responsible for relaunching between vLLM cells. Runs
that call the wrong model_id will 404 or return the wrong weights.

## Output layout

```
~/.forge-oh/bench_pathF/<TS>_run/
├── manifest.json
├── c11__debug.json
├── c11__arch.json
├── c11__plan.json
├── c03b__debug.json
├── ...
```

Each cell x prompt JSON adds (vs Path E):

```json
{
  "gpu_aggregate": {
    "runs": 3,
    "runs_with_samples": 3,
    "samples_total": 174,
    "gpu_util_avg_pct": 87.4,
    "gpu_util_max_pct": 100,
    "vram_avg_mib": 22138.5,
    "vram_max_mib": 22412,
    "gpu_temp_avg_c": 68.3,
    "gpu_temp_max_c": 74,
    "power_avg_w": 385.2,
    "power_max_w": 418.0
  },
  "runs_gpu": [ { ...run 1 GpuStats... }, { ...run 2... }, { ...run 3... } ],
  "sample_interval_s": 0.5
}
```

## Scope

Path F does NOT redefine cells — it re-benches the ADR-013 shortlist with
instrumentation. Cell definitions are copied verbatim from
`bench/pathE_qwen36_27b/bench_pathE.py`. F.3b new arch task and Tier 1
(LiveCodeBench-v6) + Tier 2 (SWE-bench Verified) land in follow-up
slices.
