# Forge-OH — Session Handoff

Overwrite this file at the end of every session. Reflects current state only.

---

## Current stage
**OFF-PLAN F.18b** — router made backend-configurable + vLLM lifecycle scripts.
Head-to-head Ollama vs vLLM bench is mid-flight; awaiting Phase 2 rerun after
first vLLM Phase 2 attempt failed 52/52 because vLLM had been killed and
never restarted.

## What was completed this session
- F.18 vLLM 0.10.2 standalone confirmed serving qwen3-coder-30b at :8500
  (see BUILD_LOG 2026-08-03 13:45 EDT for the full failure archaeology).
- 4 DEBUG_LOG entries added: venv orphaned by OS upgrade, GGUF bf16 rejection,
  triton Python.h prereq, FlashInfer SM_120 whitelist gap.
- Head-to-head bench script + runner authored in `~/dev/forge-oh/scripts/`
  (NOT yet committed; `.gitignore` excludes `scripts/` — future scripts need
  `git add -f`).
- Ollama Phase 1 baseline captured:
  `~/.forge-oh/bench/20260803_1343/ollama.csv` — 52/52 OK.
  - short_code (c=1): TTFT 1.5s / total 7.0s / 10.9 tok/s
  - code_review     : 1.0s / 12.7s / 12.5 tok/s
  - refactor        : 1.6s / 38.4s / 12.1 tok/s
  - long_context 8K : 10.6s / 16.8s / 3.9 tok/s
- vLLM Phase 2 first attempt: 52/52 CONNECTION FAILURES (vLLM was down).
- Router refactored: `LLM_PRIMARY_BACKEND` env knob (ollama|vllm), corrected
  `VLLM_URL` and `VLLM_FALLBACK_MODEL` defaults, `/api/settings/model-routing`
  exposes new fields, unit tests added, `.env.example` updated.
- vLLM lifecycle scripts (`vllm_start.sh` rewritten, new `vllm_stop.sh`,
  `vllm_status.sh`) — atomic cleanup so no ghost EngineCore workers.

## What remains before the current DoD
1. Confirm vLLM is up on Colossus (relaunch in progress — awaiting READY).
2. Rerun Phase 2 bench cleanly, decide winner.
3. Set `LLM_PRIMARY_BACKEND` in `.env.local` accordingly, restart BFF, smoke
   test routing. No code change needed to swap.
4. Return to plan Step 1 (real OpenHands agent-server on Colossus).

## Open questions / ambiguity
- Bench decision (Ollama vs vLLM primary) pending Phase 2 data.
- Bench scripts (`bench_ollama_vs_vllm.sh`, `bench_runner.py`) still
  uncommitted — commit after they've been shaken out by the rerun.

## Exact next action
On Colossus, once vLLM shows READY (or after checking with
`./scripts/vllm_status.sh`):

```bash
# Fresh bench dir to avoid mixing old failures
BENCH_DIR=~/.forge-oh/bench/$(date +%Y%m%d_%H%M)
mkdir -p "$BENCH_DIR"
BENCH_DIR="$BENCH_DIR" bash ~/dev/forge-oh/scripts/bench_ollama_vs_vllm.sh

# Then summarize
python3 ~/dev/forge-oh/scripts/bench_summarize.py "$BENCH_DIR"
```

## Ambient at session end
- vLLM: relaunching at :8500 (via updated `vllm_start.sh`).
- Ollama: stopped (killed for clean Phase 2 rerun).
- BFF: stopped.
- Colossus VRAM prior to relaunch: 722 MiB used / 31 GB free.
