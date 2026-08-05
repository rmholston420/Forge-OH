# Kosmos Session Handoff — 2026-08-05 05:45 EDT

## Current build-sequencing position

- **Stage / phase:** F.3 (Track 1, in-progress) + Stage-1H (Track 2, spec filed, impl not started)
- **Plugin / kernel component:** Bench harness (Track 1) + Harness Engineering SWE-bench sandbox port (Track 2)
- **Port(s) in progress:** none actively — spec-only turn for Track 2; Track 1 harness generation is the next action

## Completed this session

- F.1a NVML sampler + 1-cell smoke test.
- F.1b full instrumented rebench (c11, c03b, c01) + 3-scorer Council scoring pass.
- F.2 arch_v2 gold generation.
- ADR-013 amendment #1 — coder ratified as Qwen3.6-27B INT4 AutoRound (c01), planner ratified as DSR1-Distill-32B AWQ.
- F.3 pivot: drop LiveCodeBench-v6, promote SWE-bench Verified as the sole Tier-2 validation.
- F.3 setup verification on Colossus: swebench 4.1.0 installed in fresh `~/.forge-oh/bench-venv`, Verified dataset (500 tasks) loaded, v4 CLI shape confirmed, difficulty + repo distribution captured, calibration task chosen (django__django-10914).
- **This turn:** authored ADR-015 (Proposed) + `docs/reconciliation-plan-stage-1H.md` locking in Stage-1H for full-Forge-OH SWE-bench Verified acceptance. Split-track plan documented.

## Remaining before current Definition of Done

**Track 1 (F.3 Path A, coder ratification):**
1. Generate F.3 Path A shakeout harness under `bench/pathF_swebench/` (Perplexity Computer, next turn).
2. Run 8-task shakeout on Colossus (~30 min).
3. If Green: 500-task full run overnight.
4. Score pass@1, file ADR-013 amendment #2.
5. Then: resume `slice/dual-mode-routing-impl` (git stash pop) with canonical models.

**Track 2 (Stage-1H, product acceptance — spec filed, impl deferred):**
- 1H.1 preset `ap-3 = forge-oh-local-coder` (non-default).
- 1H.2 `bff/services/swe_bench_sandbox.py` + `CreateRunRequest` extension.
- 1H.3 minimum UI field.
- 1H.4 (optional) preset default flip.
- 1H.5 Path B rerun → possible ADR-013 amendment #3.

## Open questions / awaiting user answer

- None. User chose "make the optimal choices" for Stage-1H shape; all four ambiguities resolved (Stage-1H numbering, preset default deferred, narrow sandbox scope, minimum UI field).

## Exact next action

Perplexity Computer generates F.3 Path A shakeout harness — `bench/pathF_swebench/harness_shakeout.py` + `bench/pathF_swebench/tasks_shakeout.json` + `bench/pathF_swebench/README.md` — following `local-llm-bench` + `forge-oh-bench-methodology` skills. Uses oracle mode (problem statement + files gold patch touches). 8 tasks (calibration = django__django-10914). Output → `~/.forge-oh/bench_pathF/<UTC>_run/`. User reviews harness before pasting Colossus run commands.
