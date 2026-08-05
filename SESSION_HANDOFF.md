# Forge-OH Session Handoff — 2026-08-05 05:14 EDT

## Current build-sequencing position

- **Stage / phase:** F.3 (renumbered) — SWE-bench Verified validation of ratified coder (c01 Qwen3.6-27B INT4 AutoRound).
- **Plugin / kernel component:** `bench/pathF_swebench/` (to be created).
- **Port(s) in progress:** none — bench-only slice. Coder :8501 (c01) is the consumer.

## Completed this session

- F.1a NVML sampler smoke test on c11 (Devstral-24B AWQ) — instrumentation validated, VRAM-conflict-free once planner torn down.
- F.1b full instrumented rebench: 3 cells × 3 prompts × (1 warmup + 3 scored runs), 500ms NVML sampling. Completed 04:32–04:39 EDT.
- F.2 arch_v2 gold generation — new `bench/prompts/arch_v2_router.txt` (prompt-solvable router-design task) + 3-Council gold + Opus 5 synthesis at `/home/user/workspace/gold-arch_v2-council-synthesis.md`.
- F.1b Council scoring — 3 scorers (Claude Fable 5, GPT 5.6 Sol, Gemini 3.1 Pro) unanimously ranked `c01 > c11 > c03b` (112.7 > 101.0 > 73.0 /200 combined avg, 39.7-point margin over 3rd).
- **ADR-013 amendment #1 filed and pushed** — c01 (Qwen3.6-27B INT4 AutoRound) ratified as canonical coder. All BFF + launcher configs flipped, PORTING_LEDGER entry #3 added, BUILD_LOG updated, pushed as commit `2661a8c` on `slice/coder-planner-rebench`.
- **Operator brought c01 live on Colossus** — `qwen3.6-27b-int4-autoround` serving on :8501 (READY after 210s), planner back up on :8511, BFF restarted, all 3 forge-oh services healthy.
- **F.3 pivot decision** — LiveCodeBench-v6 dropped due to release-window contamination (v6 covers Apr 2025, all our candidates released after). F.5 SWE-bench Verified promoted to F.3 as the sole Tier-2 validation. Documented in BUILD_LOG 2026-08-05 05:14 EDT entry.

## Remaining before current Definition of Done

F.3 (SWE-bench Verified on c01) has not been started this session. Next-session tasks:

1. **Verify SWE-bench packaging + Docker requirements on Colossus** — check whether `pip install swebench` (Princeton NLP eval package) works cleanly or whether we need to clone the repo. Confirm Docker sandbox model (SWE-bench spins up one container per task for isolated eval).
2. **Vendor SWE-bench Verified** — dataset from `princeton-nlp/SWE-bench_Verified` on HF (MIT-licensed, 500 problems). Log in `PORTING_LEDGER.md` as entry #4.
3. **Create `bench/pathF_swebench/` harness:**
   - Loader over the 500-problem Verified subset.
   - Agentic loop wired to c01 via :8501 (or via full BFF stack :8081 if we want end-to-end signal).
   - Pass@1 metric with the standard SWE-bench Verified evaluator.
   - Docker sandbox per task.
   - Time-limit guard: kill run at 12h wall time if incomplete; report partial-corpus verdict.
4. **Dry run on 5-10 problems** to establish per-problem wall time before committing to the full 500-task overnight run.
5. **Full run + verdict** — commit results to BUILD_LOG with per-category pass rate + total wall time.
6. **ADR-013 amendment #2** — SWE-bench verdict (confirming or overturning F.1b).
7. **After F.3 done: resume `slice/dual-mode-routing-impl`** (git stash pop).

## Open questions / awaiting user answer

- **SWE-bench harness path:** direct c01 :8501 (fastest, isolates model quality) or full BFF+agent-server stack :8081 (slower, tests production integration path). Default = direct :8501 for the validation run; production-integration test comes later.
- **Full 500-task budget:** ~4-8h optimistic estimate; may exceed 12h with retries + slow tasks. If dry run shows >90s/problem, we cap the run at a random 200-problem subset instead of full 500.

## Exact next action

**Agent next-session step 1** — verify SWE-bench Verified packaging (should be doable in 5 min):

```bash
# On Colossus
python -c "import swebench; print(swebench.__version__)" 2>&1 || pip show swebench
# If not installed, check:
pip install swebench --dry-run 2>&1 | head -20

# Verify Docker + swebench evaluator container availability:
docker images | grep -E 'swebench|princeton'
```

**Agent next-session step 2** — inspect the Verified dataset to confirm 500-problem count + license + schema:

```bash
python -c "
from datasets import load_dataset
ds = load_dataset('princeton-nlp/SWE-bench_Verified', split='test')
print(f'Rows: {len(ds)}')
print(f'Columns: {ds.column_names}')
print(f'Sample instance_id: {ds[0][\"instance_id\"]}')
"
```

**Agent next-session step 3** — draft `bench/pathF_swebench/README.md` scoping the harness before writing code, gate on user approval before proceeding.

**Current Colossus state (verified 05:10 EDT):**
- Coder :8501 serving `qwen3.6-27b-int4-autoround` (F.1b-ratified c01)
- Planner :8511 serving DSR1-Distill-32B-AWQ (ADR-013 planner-ratified)
- BFF :8081, agent-server :8090, Next.js :3000 — all healthy per `scripts/forge-status.sh`
- No git stash pending on `slice/coder-planner-rebench`
- `slice/dual-mode-routing-impl` still has WIP stashed (from prior session)
