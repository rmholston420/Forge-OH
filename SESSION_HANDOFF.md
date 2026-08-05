# Forge-OH Session Handoff — 2026-08-05 07:04 EDT

## Current build-sequencing position
- **Stage / phase**: Track 1 — F.3 Path A (SWE-bench Verified pass@1 on raw c01, oracle-retrieval)
- **Plugin / kernel component**: bench harness
- **Port(s) in progress**: —

## Completed this session
- F.3.0 dry-run PASSED: c01 produced correct fix for django__django-10914 (3.4s, 41.46 tok/s, 143 completion tokens)
- Fence-stripping fix committed (`73cc32a`): c01 wraps output in ```diff ... ``` — normalize_patch() strips fences, patch_raw preserves original
- F.3 docker glue implemented (HEAD): `apply_patch_and_run_tests()` calls the official swebench harness. Artifacts under `~/.forge-oh/swebench_runs/<harness_run_id>/`
- Coder/planner VRAM coexistence documented in DEBUG_LOG (2026-08-05 06:52 EDT)

## Remaining before current Definition of Done
- **F.3.0 docker-real confirmation** (user, next step):
  1. `source ~/dev/forge-oh/.oh-venv/bin/activate`
  2. `pip install swebench` (Python 3.12 in .oh-venv, meets ≥3.10)
  3. `df -h ~ /var/lib/docker` — confirm ≥30 GB free (harness pulls one image ≈ few GB)
  4. `git pull && python -m bench.pathF_swebench.bench_pathF_swebench --tasks django__django-10914 --model c01`  (note: NO `--dry-plan-only`)
  5. Expected: `resolved=true` for django__django-10914 (ground-truth patch matches c01 output)
- **F.3.1 full-500 run** (Perplexity Computer + user overnight): only after F.3.0 docker-real green. Expected wall 4-8h. Disk-space check first (harness pulls ~500 images, ~120 GB per official docs).
- **ADR-013 amendment #2**: after F.3.1 completes → record pass@1 verdict.
- **Post-F.3**: `docker start forge-vllm-planner` to restore steady-state.
- Non-blocking backlog: untracked `scripts/*.sh` parity per ADR-016; stale docker containers (`uia-qdrant`, `mythos_v01-*`, `open-notebook-*`); stale git stashes.

## Open questions / awaiting user answer
- None. Next step is a user-runs-on-Colossus confirmation.

## Exact next action
```bash
source ~/dev/forge-oh/.oh-venv/bin/activate
pip install swebench
df -h ~ /var/lib/docker
cd ~/dev/forge-oh && git pull
python -m bench.pathF_swebench.bench_pathF_swebench --tasks django__django-10914 --model c01
```
