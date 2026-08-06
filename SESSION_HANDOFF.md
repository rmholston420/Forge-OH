# Forge-OH Session Handoff — 2026-08-06 18:46 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 8 (SDK-native capability slices) — see `docs/reconciliation-plan-v1.md` and its stage-8 companion.
- **Slice in progress:** none. Slice 8.0.5 (measurement hardening) closed this session. §8.1 unblocked.
- **Plugin / kernel component:** N/A this session — `bench/` measurement infrastructure only.
- **Port(s) in progress:** none.

## Completed this session

- **Slice 8.0.5 measurement hardening** — see BUILD_LOG 2026-08-06 18:46 EDT for full detail.
  - New `bench/lib/mcnemar.py` (stdlib-only mid-p McNemar with chi-square continuity fallback at n_discordant≥25) + `bench/lib/test_mcnemar.py` (6 tests, all pass).
  - Harness `bench/pathF_swebench/bench_pathF_swebench.py` extended: `--task-count {30,100}`, `--pair-with BASELINE_RUN_DIR`, `--usd-per-gpu-hour`, new `_emit_summary` telemetry fields (`gpu_seconds_total`, `wall_seconds_total`, `gpu_seconds_per_solved_task`, `wall_seconds_per_solved_task`, `usd_per_solved_task`, `usd_per_gpu_hour_assumed`), plus manifest provenance fields.
  - New `scripts/generate_smoke_100.py` — reproduces the seed=42 stratified sampling recipe to expand SMOKE_TASK_IDS to 100. Runs on Colossus once against the F.3 full-500 log.
  - `docs/reconciliation-plan-stage-8.md` §8.0.5 drafted at full scope-DoD-stop-condition structure. §8.9 placeholder renumbered to §8.1–§8.9.
  - Retrospective McNemar analytically proven: for any 10/30 vs 9/30 pairing, mid-p ∈ [0.50, 0.81]. p > 0.05 is a mathematical certainty at this Δ (Case A max-overlap b=1,c=0 → 0.500; Case B min-overlap b=2,c=1 → 0.625; Case C extreme-discordancy b=9,c=8 → 0.815).

## Remaining before current Definition of Done is met

Slice 8.0.5 DoD is fully met. No slice currently in progress.

**Optional follow-ups outside 8.0.5's DoD:**

1. Populate `SMOKE_100_TASK_IDS` by running the generator on Colossus and committing the result. Non-blocking for §8.1 unless §8.1 wants a 100-task run.
2. Empirical confirmation of the retrospective McNemar on the actual per-task JSONs (analytical proof already covers DoD item 4; the empirical run is confirmation, not risk):
   ```
   cd ~/dev/forge-oh && python3 -m bench.lib.mcnemar \
     ~/.forge-oh/bench_pathF_swebench/20260806_1211_run \
     ~/.forge-oh/bench_pathF_swebench/20260806_1647_run
   ```
   Expected: p between 0.50 and 0.81, method = midp_exact.

## Open questions / awaiting user answer

None. All Slice 8.0.5 design choices were taken under standing "make optimal choice" delegation and are documented in the BUILD_LOG entry (mid-p McNemar, deterministic strict-prefix 30→100 expansion, USD_PER_GPU_HOUR=0.60 default).

**Next slice choice:** Council-Synthesis line 103 mandates strict order §8.0 → §8.0.5 → §8.1 → §8.2. §8.1 is the next slice per that ordering (unless the user wants to revisit spec-decode or draft the planner-role bench first as a §8.0c interlude).

## Exact next action

At start of next session, if continuing to §8.1:

```
cd ~/dev/forge-oh
git pull
tail -50 BUILD_LOG.md   # confirm Slice 8.0.5 close entry present
python3 -m bench.lib.test_mcnemar   # confirm harness still passes on Colossus
```

Then read Council-Synthesis §8.1 anchor and `docs/reconciliation-plan-stage-8.md` for §8.1's scope, and draft the §8.1 section following the §8.0 / §8.0.5 pattern before writing any code.

If populating SMOKE_100 first (recommended as a lightweight prelude to §8.1):

```
cd ~/dev/forge-oh
python3 scripts/generate_smoke_100.py \
    ~/.forge-oh/bench_pathF_swebench/20260805_1025_run/ \
    > /tmp/smoke_100.txt
# Review /tmp/smoke_100.txt, then paste the list body between the
# <SMOKE_100_START>/<SMOKE_100_END> markers in
# bench/pathF_swebench/bench_pathF_swebench.py, commit, push.
```
