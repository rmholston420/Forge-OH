# Forge-OH Session Handoff — 2026-08-05 06:55 EDT

## Current build-sequencing position
- **Stage / phase**: Track 1 — F.3 Path A (SWE-bench Verified pass@1 on raw c01, oracle-retrieval)
- **Plugin / kernel component**: bench harness
- **Port(s) in progress**: —

## Completed this session
- ADR-016 ratified (Colossus↔GitHub parity, commit `33f5221`)
- Envelope drift fix (`6c024ef`) + error boundaries (`9b3f777`)
- Reconciliation-plan-v1 canonical, supersedes Action-Plan-v4 (`3cc425a`)
- F.3 Path A shakeout harness scaffolded (`5c1e9b6`) + error-path fix (`62341aa`)
- **F.3.0 dry-run PASSED**: c01 produced correct fix for `django__django-10914` in 3.45s @ 41.46 tok/s
- Fence-stripping fix committed (this HEAD): c01 wraps output in ```diff``` fences that `git apply` rejects
- DEBUG_LOG entry for the planner/coder VRAM coexistence constraint

## Remaining before current Definition of Done
- **F.3.0 confirm**: user reruns dry-run to verify fence-strip works (should see `patch` field with no fences + `patch_raw` field with fences)
- **F.3 follow-up (Perplexity Computer)**: implement `apply_patch_and_run_tests` in `apply_and_test.py`. 8-step reference in module docstring. Correct docker image namespace: resolve via installed `swebench` package (not hardcoded `swebench/sweb.eval.x86_64.*`).
- **F.3.1 full-500 run**: only after docker glue lands. Real wall estimated 4-8h (docker overhead dominates the 29-min inference budget). Overnight run.
- **ADR-013 amendment #2**: after F.3.1 completes → record pass@1 verdict.
- **Post-F.3**: `docker start forge-vllm-planner` to restore steady-state.
- Non-blocking backlog: untracked `scripts/*.sh` parity per ADR-016; stale docker containers (`uia-qdrant`, `mythos_v01-*`, `open-notebook-*`); stale git stashes.

## Open questions / awaiting user answer
- None. F.3.0 confirm is a user-runs-on-Colossus step.

## Exact next action
1. User: `cd ~/dev/forge-oh && git pull`
2. User: rerun F.3.0 dry-run to verify fence-strip:
   ```bash
   python -m bench.pathF_swebench.bench_pathF_swebench --tasks django__django-10914 --model c01 --dry-plan-only
   ls -1t ~/.forge-oh/bench_pathF_swebench/*_run/django__django-10914.json | head -1 | xargs python3 -c "
   import json, sys
   d = json.load(open(sys.argv[1]))
   print('normalized patch starts:', d['patch'][:60])
   print('raw patch has fence:', '\`\`\`' in d.get('patch_raw',''))
   print('normalized patch has fence:', '\`\`\`' in d['patch'])
   "
   ```
3. Perplexity Computer: implement docker apply-and-test glue (F.3 follow-up commit).
