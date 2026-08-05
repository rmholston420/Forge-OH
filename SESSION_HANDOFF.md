# Kosmos / Forge-OH Session Handoff — 2026-08-05 07:31 EDT

## Current build-sequencing position
- **Stage / phase:** F.3 Path A · smoke-25 rerun after context-budgeting fix
- **Plugin / kernel component:** `bench/pathF_swebench/`
- **Port(s) in progress:** none (bench-only)

## Completed this session
- F.3.0 docker-real GREEN (django-10914 resolved)
- Numbered tasks + progress.json + ETA
- NVML sampler promoted to `bench/_common/`; ADR-017 ratified
- **Dynamic max_tokens budgeting + truncation tracking** — fixes the two bugs smoke-25 exposed at task 9 (context overflow) and task 7 (silent length truncation)

## Remaining before current Definition of Done
1. User: Ctrl-C the current smoke-25 run (if still going)
2. User: `cd ~/dev/forge-oh && git pull` — pulls HEAD with numbering + NVML + context-budgeting fix
3. User: rerun smoke-25 CLEAN (fresh run dir, not resume — the earlier bad results should be dropped)
4. Agent: score smoke-25 against comparison anchors (17/25 stretch, 13/25 anchor-par)
5. Agent: if green, kick full-500 with `--tasks all --resume-run`
6. Agent: ADR-013 amendment #2 with F.3 verdict
7. Agent: `docker start forge-vllm-planner` after full-500

## Open questions / awaiting user answer
- None. Fix is optimal choice per user's standing directive.

## Exact next action
```bash
# In the shell where smoke-25 is running:
^C

# Then a fresh shell:
cd ~/dev/forge-oh && git pull
# Fresh run dir (do NOT --resume-run; the interrupted run has buggy data):
.oh-venv/bin/python -m bench.pathF_swebench.bench_pathF_swebench --smoke-25 --model c01

# Live-tail from another shell:
watch -n 5 'jq . ~/.forge-oh/bench_pathF_swebench/$(ls -1t ~/.forge-oh/bench_pathF_swebench/ | head -1)/progress.json'
```

Watch each task line for `toks=X/Y` — Y is the budgeted max, not the ceiling. If Y < 4096 you'll see it in the log. And if a prompt is > ~32200t, the task is skipped as `context-budget-skip` rather than 400ing.
