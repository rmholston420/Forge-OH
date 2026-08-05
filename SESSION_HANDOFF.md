# Forge-OH Session Handoff — 2026-08-05 05:58 EDT

## Current build-sequencing position

- **Stage / phase:** F.3 (Track 1, in-progress) + Stage-1H (Track 2, ADR
  filed) + **ADR-016 (Ratified this turn, cross-cutting)**
- **Plugin / kernel component:** Bench harness (Track 1) + Harness
  Engineering SWE-bench sandbox (Track 2) + repo hygiene (ADR-016)
- **Port(s) in progress:** none actively — next action is generating F.3
  Path A shakeout harness

## Completed this session

- F.1a NVML sampler + 1-cell smoke test.
- F.1b full instrumented rebench (c11, c03b, c01) + 3-scorer Council
  scoring pass.
- F.2 arch_v2 gold generation.
- ADR-013 amendment #1 — coder ratified as Qwen3.6-27B INT4 AutoRound (c01),
  planner ratified as DSR1-Distill-32B AWQ.
- F.3 pivot: drop LiveCodeBench-v6, promote SWE-bench Verified as sole
  Tier-2 validation.
- F.3 Colossus setup verification: swebench 4.1.0, Verified dataset (500
  tasks), v4 CLI, calibration task chosen.
- **ADR-015 (Proposed)** — Stage-1H SWE-bench end-to-end sandbox (per-run
  Docker + preset routing + minimum UI).
- **ADR-016 (Ratified this turn)** — Colossus<->GitHub mirror parity.
  Direct-to-GitHub commit workflow established; paste-block-for-commit
  retired (previous paste block killed operator's bash session).
  Enforcement: AGENTS.md Rules #9 + #10, forge-doctor Section 10,
  pre-commit hook.

## User action required on Colossus (post-pull)

```bash
cd ~/dev/forge-oh
git pull
rm docs/proposals/2026-08-04-smoke-*.md   # 35 failed-proposer noise files
rm docs/selfeval/2026-08-04-selfeval.json # failed-selfeval JSON (all env errors)
# optional pre-commit install (one-time):
source .oh-venv/bin/activate
pip install pre-commit
pre-commit install
# verify parity:
bash scripts/forge-doctor.sh   # Section 10 should show "OK no drift"
```

## Remaining before current Definition of Done

**Track 1 (F.3 Path A, coder ratification):**
1. Perplexity Computer generates F.3 Path A shakeout harness under
   `bench/pathF_swebench/` (next commit on this branch).
2. User runs 8-task shakeout on Colossus (~30 min).
3. If Green: 500-task full run overnight.
4. Score pass@1, file ADR-013 amendment #2.
5. Resume `slice/dual-mode-routing-impl` (git stash pop) with canonical
   models.

**Track 2 (Stage-1H, product acceptance — spec filed, impl deferred):**
- 1H.1 preset `ap-3 = forge-oh-local-coder` (non-default).
- 1H.2 `bff/services/swe_bench_sandbox.py` + `CreateRunRequest` extension.
- 1H.3 minimum UI field.
- 1H.4 (optional) preset default flip.
- 1H.5 Path B rerun -> possible ADR-013 amendment #3.

## Open questions / awaiting user answer

- None. (Direct-to-GitHub workflow now the standing rule per ADR-016.)

## Exact next action

Perplexity Computer generates F.3 Path A shakeout harness — commits
directly to `slice/coder-planner-rebench`:
- `bench/pathF_swebench/harness_shakeout.py`
- `bench/pathF_swebench/tasks_shakeout.json`
- `bench/pathF_swebench/prompts/oracle_template.txt`
- `bench/pathF_swebench/README.md`

Following `local-llm-bench` + `forge-oh-bench-methodology` skills. Oracle
mode. 8 tasks (calibration = django__django-10914). Output ->
`~/.forge-oh/bench_pathF/<UTC>_run/`.
