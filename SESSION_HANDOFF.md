# Session Handoff — 2026-08-03 13:50 EDT

## Current State
- **F.16 (GPU monitor + sparkline popover)**: COMPLETE + Colossus-verified.
- **G.1 (self-testing)**: COMPLETE + Colossus-verified.
- **F.18 (vLLM standalone, OFF-PLAN)**: vLLM 0.10.2 serving `qwen3-coder-30b` GGUF on `127.0.0.1:8500`. First chat completion successful. VRAM 28.8 GB / 32 GB at `--gpu-memory-utilization 0.85`. Cannot coexist with Ollama on same GPU.

## In Progress
- **Head-to-head bench: Ollama vs vLLM** on qwen3-coder-30b, num_ctx=32768, 4 prompts × 3 concurrency levels (1, 4, 8).
  - Script: `~/dev/forge-oh/scripts/bench_ollama_vs_vllm.sh` (not committed — lives on Colossus only).
  - Runner: `~/dev/forge-oh/scripts/bench_runner.py`.
  - Output: `~/.forge-oh/bench/YYYYMMDD_HHMM/{ollama,vllm}.csv` + `summary.md`.
  - Sequential (single GPU): Ollama phase → shut down → vLLM phase → summary.
- Decides which backend is primary vs fallback in the BFF router.

## Remaining Before Current DoD
- [ ] Bench completes and yields a decision.
- [ ] Wire winning backend into BFF router env vars (`VLLM_URL`, `VLLM_FALLBACK_MODEL` or the reverse).
- [ ] Restart BFF, curl through router, confirm fallback path.
- [ ] Fix `vllm_start.sh` watchdog false-negative in ad-hoc launch loops (loop checks `vllm serve` but child is named `VLLM::EngineCore`, so healthy child looked dead).

## Open Questions Awaiting User Answer
- None right now.

## Exact Next Action
1. Wait for bench to finish (~10-15 min from 2026-08-03 13:44 start).
2. Read `summary.md`, decide primary/fallback.
3. Set BFF env vars accordingly, restart BFF, smoke-test router.
4. Then return to plan Step 1 (real OpenHands agent-server on Colossus).

## Ambient
- Ollama: currently stopped for bench.
- BFF: currently stopped for clean bench isolation.
- Frontend dev server: not running.
- vLLM: managed by the bench script (started/stopped between phases).
