# Kosmos / Forge-OH Session Handoff — 2026-08-05 07:34 EDT

## Current build-sequencing position
- **Stage / phase:** F.3 Path A · smoke-25 clean rerun after tokenize-URL fix
- **Plugin / kernel component:** `bench/pathF_swebench/`

## Completed this session
- F.3.0 GREEN, numbering + progress.json + NVML sampler, dynamic max_tokens budgeting, ADR-017
- **Tokenize URL fix**: vLLM's `/tokenize` lives at BASE, not under `/v1`. Fixed URL construction.

## Remaining before current Definition of Done
1. User: Ctrl-C current smoke-25 run (BEFORE task 9 = matplotlib__matplotlib-24149, or it will 400)
2. User: `cd ~/dev/forge-oh && git pull` — pulls tokenize URL fix
3. User: fresh smoke-25 (no --resume-run, the interrupted run's data is bad)
4. Agent: score against anchors

## Exact next action
```bash
^C
cd ~/dev/forge-oh && git pull
.oh-venv/bin/python -m bench.pathF_swebench.bench_pathF_swebench --smoke-25 --model c01
```

Watch: each task should now show `toks=X/Y` with Y varying (e.g. 4096 for small prompts, ~3800 for medium, ~500 for near-overflow prompts, or "context-budget-skip" if the prompt itself won't leave 512t room).
