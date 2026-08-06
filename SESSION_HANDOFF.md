# Forge-OH Session Handoff — 2026-08-06 15:30 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 8 · Slice 8.0 (vLLM serving-infra config bundle)
- **Plugin / kernel component:** coder role · vLLM launcher · Docker path (canonical per ADR-013 amendment #1)
- **Ports / adapters in progress:** `ops/vllm_launch_coder.sh` on :8501 — flag bundle applied, awaiting Colossus-side restart + smoke re-baseline for DoD attestation.

## Completed this session

- Read Council-Synthesis §8.0 slice contract, KNOWN_ISSUES §68, `bench/pathE_qwen36_27b/vllm_launch.sh:195`, DEBUG_LOG 2026-08-03 18:34 EDT, ADR-013 amendment #1, ADR-029 D4.
- Drafted `docs/reconciliation-plan-stage-8.md` §8.0 (initial draft targeted the wrong launcher `scripts/vllm_start.sh`; corrected within the session to `ops/vllm_launch_coder.sh`).
- **Verified vLLM 0.26.0** in `vllm/vllm-openai:latest` via `docker run --rm --entrypoint python3 vllm/vllm-openai:latest -c 'import vllm; print(vllm.__version__)'`. Well above 0.10 threshold.
- **Filed KNOWN_ISSUES entry** for `~/venv/vllm-new` HF Hub 1.26 vs transformers <1.0 conflict (deferred to F.19.5; not on any live Slice 8.0 path).
- **Filed DEBUG_LOG entry** for the malformed `vllm --version` probe (missing `--gpus all` + wrong entrypoint semantics).
- **Discovered BFF has no agent-compose site**: BFF forwards runs to OpenHands agent-server on :8090; `LLMSummarizingCondenser` lives inside that process. DoD item 6 (condenser alignment) moved to Slice 8.6. ADR-029 D4 amended inline.
- **Executed Slice 8.0 flag bundle** on `ops/vllm_launch_coder.sh`: 4 flags added (`--kv-cache-dtype fp8`, `--enable-chunked-prefill`, `--long-prefill-token-threshold 4096`, `--speculative-config` n-gram), 1 flag modified (`--max-model-len 32768 → 65536`), 0 flags removed. `bash -n` clean. Zero code touched outside the launcher.
- Committed and pushed all changes.

## Remaining before Slice 8.0 Definition of Done

1. User restarts coder container:
   ```bash
   ~/dev/forge-oh/ops/vllm_supervisor.sh down coder
   ~/dev/forge-oh/ops/vllm_supervisor.sh up coder
   ```
   Wait up to 900s for container health. Verify:
   ```bash
   curl -sf http://127.0.0.1:8501/v1/models | python3 -m json.tool
   ```
   Should list `qwen3.6-27b-int4-autoround`. DoD items 1 + 2.
2. User re-runs smoke-30 at concurrency=1 against the same 30 tasks that produced Path A pass@1 = 33.3% baseline at `~/.forge-oh/bench_pathF_swebench/20260806_1211_run/`:
   ```bash
   cd ~/dev/forge-oh && \
     python3 bench/pathF_swebench/bench_pathF_swebench.py \
       --tasks all --model c01 --concurrency 1
   ```
3. DoD attestation (agent side, once results returned):
   - **DoD 4**: pass@1 ≥ 32.0% (regression ≤ 1 task from 33.3% baseline). If worse, agent walks the §Rollback strategy bisect.
   - **DoD 5**: `django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248` no longer show `context-budget-skip` — they load and either pass or fail through the model.
4. Agent appends BUILD_LOG attestation entry + overwrites SESSION_HANDOFF pointing to Slice 8.0b (planner-side mechanical copy). Commits and pushes.

## Open questions / awaiting user answer

None blocking. All draft-time questions (Q1 vLLM version resolved 0.26.0, Q2 spec-decode acceptance deferred to §8.0.5, Q3 APC block-size deferred to §8.6) are handled.

## Exact next action

Paste on Colossus:

```bash
cd ~/dev/forge-oh && git pull

# Restart coder with the Slice 8.0 flag bundle.
./ops/vllm_supervisor.sh down coder
./ops/vllm_supervisor.sh up coder

# Wait for it to warm up (cold start ~2–3 min; up to 900s tolerated).
# Poll until /v1/models responds:
for i in $(seq 1 90); do
  if curl -sf http://127.0.0.1:8501/v1/models > /dev/null; then
    echo "coder ready after ${i}0s"
    curl -s http://127.0.0.1:8501/v1/models | python3 -m json.tool
    break
  fi
  sleep 10
done

# Re-run smoke-30 (matches F.3.0 concurrency=1 baseline conditions).
# Must run as a module from repo root (not as a script) so bench.pathF_swebench.*
# imports resolve. See DEBUG_LOG 2026-08-06 15:37 EDT.
cd ~/dev/forge-oh && \
  python -m bench.pathF_swebench.bench_pathF_swebench \
    --tasks all --model c01 --concurrency 1 2>&1 | tee ~/.forge-oh/bench_pathF_smoke30_slice8.0.log
```

Return: (a) the `/v1/models` JSON, (b) the final pass@1 line from the smoke-30 run, (c) whether the 4 previously-context-skipped tasks now show a real pass/fail instead of `context-budget-skip`.

If pass@1 < 32.0%, I execute the §Rollback strategy bisect from `docs/reconciliation-plan-stage-8.md`.
