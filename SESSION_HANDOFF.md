# Kosmos / Forge-OH Session Handoff — 2026-08-05 07:20 EDT

## Current build-sequencing position
- **Stage / phase:** F.3 Path A · SWE-bench Verified oracle-retrieval on ratified coder c01 (Qwen3.6-27B INT4 AutoRound @ :8000)
- **Plugin / kernel component:** `bench/pathF_swebench/` (harness), `bench/_common/` (shared sampler)
- **Port(s) in progress:** none (bench-only)

## Completed this session
- F.3.0 docker-real gate GREEN: `django__django-10914` resolved=True, pass@1=1.0, wall 46.82s
- F.3 harness got numbered tasks + progress.json + ETA
- Promoted `nvml_sampler.py` to `bench/_common/`; F.1b compat shim in place
- Wired GpuSampler into F.3: `gpu_inference` + `gpu_harness` per task, `gpu` aggregate in summary.json
- ADR-017 ratified: NVML sampling mandatory on every bench harness

## Remaining before current Definition of Done (F.3 verdict)
1. User: `cd ~/dev/forge-oh && git pull`
2. User: verify NVML sampler works — `.oh-venv/bin/python -m bench._common.nvml_sampler` should print a smoke-sample dict with `nvml_available: true`. If it fails with `pynvml` ImportError, `.oh-venv/bin/pip install nvidia-ml-py` and re-verify.
3. User: run smoke-25 — see "Exact next action" below.
4. Agent: score smoke-25 results (green threshold ≥23/25 resolved = 92%).
5. Agent: if green, kick full-500 overnight (`--tasks all`) with `--resume-run` safety.
6. Agent: ADR-013 amendment #2 with F.3 pass@1 verdict.
7. Agent: `docker start forge-vllm-planner` to restore steady-state after full-500.

## Open questions / awaiting user answer
- None. User already answered: smoke-25 first, resume-run enabled, "make optimal choices" on sampling-window scope + sampler location. GPU-tracking instruction is now a permanent rule (ADR-017).

## Exact next action
On Colossus:
```bash
cd ~/dev/forge-oh && git pull
# One-time NVML smoke (only if you want to double-check before a 25-task run):
.oh-venv/bin/python -m bench._common.nvml_sampler
# Kick smoke-25:
.oh-venv/bin/python -m bench.pathF_swebench.bench_pathF_swebench --smoke-25 --model c01
# Live-tail progress from another shell:
watch -n 5 'jq . ~/.forge-oh/bench_pathF_swebench/$(ls -1t ~/.forge-oh/bench_pathF_swebench/ | head -1)/progress.json'
```
