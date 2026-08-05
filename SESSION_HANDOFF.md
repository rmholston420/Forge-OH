# Forge-OH Session Handoff — 2026-08-05 07:07 EDT

## Current build-sequencing position
- **Stage / phase**: Track 1 — F.3 Path A (SWE-bench Verified pass@1, oracle-retrieval, raw c01)
- **Plugin / kernel component**: bench harness
- **Port(s) in progress**: —

## Completed this session
- F.3.0 docker-real gate GREEN: `django__django-10914` resolved by c01 (`pass_at_1=1.0`, wall 46.82s)
- Fence-stripping fix (`73cc32a`)
- Official swebench harness integration (`1bb51d4`)
- Smoke-25 + resumption (HEAD): 25-task cross-repo smoke set + `--resume-run DIR`. All 25 IDs verified in Verified split; all 25 base_commits distinct.

## Remaining before current Definition of Done
- **F.3.0.5 smoke-25 pass** (user, next step):
  1. `cd ~/dev/forge-oh && git pull`
  2. `python -m bench.pathF_swebench.bench_pathF_swebench --smoke-25 --model c01`
  3. Expected wall: 20-60 min depending on which instance images are already cached from F.3.0. Most will need first-time pulls (~2-3 GB each).
  4. Watch stdout for per-task `ok wall=... resolved=True/False` lines.
  5. If interrupted mid-run, resume with:
     `python -m bench.pathF_swebench.bench_pathF_swebench --smoke-25 --model c01 --resume-run /home/rmholston/.forge-oh/bench_pathF_swebench/<ts>_run`
  6. **Green threshold for Go on F.3.1**: ≥90% resolved (23+/25). Below that, diagnose failures from `harness_stderr_tail` in per-task JSONs before overnight run.

- **F.3.1 full-500 overnight** (only after F.3.0.5 green): kicked off before bed; expected 6-10h wall.

- **ADR-013 amendment #2**: after F.3.1 completes → record c01 pass@1 verdict.

- **Post-F.3**: `docker start forge-vllm-planner` to restore steady-state.

- Non-blocking backlog: untracked `scripts/*.sh` parity per ADR-016; stale docker containers; stale git stashes.

## Open questions / awaiting user answer
- None. F.3.0.5 smoke-25 is a user-runs-on-Colossus step.

## Exact next action
```bash
cd ~/dev/forge-oh && git pull
python -m bench.pathF_swebench.bench_pathF_swebench --smoke-25 --model c01
```

If it goes >60 min without a per-task `ok`/`resolved=` line, `Ctrl-C` and paste last 30 lines of stdout + `ls /home/rmholston/.forge-oh/swebench_runs/ | tail -5`.
