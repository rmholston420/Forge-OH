# Forge-OH — Session Handoff

Overwrite this file at the end of every session. Reflects current state only.

---

## Current stage
**F.19-pre COMPLETE (ADR-009 accepted).** Bench + verdict + ADR
committed. Coder role → `qwen3.5-nvfp4` (vLLM). Planner role →
`qwen3-thinking-2507-awq` (vLLM). Both models are retained on disk;
neither is wired into `bff/services/model_router.py` yet — that is F.19.

Ready to start **F.19** (real router wiring for the two new endpoints).

## Ambient
- vLLM: RUNNING at :8500 serving **qwen3-coder-30b GGUF** (F.18 default,
  still in place until F.19 rewires).
- Ollama: STOPPED + systemd unit `disabled` (unchanged from F.18).
- Agent-server: RUNNING at :8090.
- BFF: RUNNING at :8081 (F.18c dotenv fix still in place).
- Frontend: RUNNING at :3000.
- The bench-run weights (`qwen3.5-nvfp4` and `qwen3-thinking-2507-awq`)
  are on disk in `~/.cache/huggingface/hub/` — see `bench/f19pre/`
  launchers for the exact revisions.
- GPU free: ~3.1 GB / 32 GB (vLLM holds ~29 GB for the F.18 model).

## What was completed this session
1. **F.19-pre bench harness** — 8 cells (2 roles × 2 runtimes × 2
   models) × 3 prompts = 24 answers.
2. **c03 Ollama qwen3.5:35b-a3b think:false BROKEN** — thinking-mode
   leaks, all 3 answers empty. Root cause: Ollama silently drops
   `chat_template_kwargs.enable_thinking=false`.
3. **c04 launched successfully** after `--max-num-seqs 128` fix for
   qwen3.5-MoE Mamba cache (documented in DEBUG_LOG entry pending in
   next session).
4. **All 24 answers scored** across correctness / completeness /
   executability / groundedness. Full table in
   `bench/f19pre/results/scores_20260803.md`.
5. **ADR-009 written and committed** to `docs/adr/009-local-llm-selection.md`.
   (Note: originally planned as ADR-0007; 007 was already taken by
   `007-verify-loop.md`. Numbering resumed at 009.)
6. **BUILD_LOG appended** with F.19-pre entry.

## What remains before Definition of Done for F.19
1. Rewire `bff/services/model_router.py` to expose two named routes:
   - `coder` → `http://localhost:8500/v1` (or new port), model
     `qwen3.5-nvfp4`.
   - `planner` → same vLLM host, model `qwen3-thinking-2507-awq`.
2. Decide launcher topology: one vLLM process per role (2 ports) or a
   single vLLM process serving both models. Single-GPU + 30 GiB VRAM
   budget likely forces **swap on demand** — plan for a small
   supervisor script under `ops/` that starts/stops the right launcher
   per request.
3. Add `/v1/models` readiness probe for whichever launcher(s) F.19
   settles on.
4. Add unit tests to `bff/tests/test_model_router.py` covering the new
   role-based routing (mirror the F.18b test structure).
5. Run a live 3-prompt smoke (P1/P2/P3 from F.19-pre) through the
   rewired router and verify the emitted answers still hit c04/c08
   quality bars.

## Open questions / ambiguity
- **Planner max_tokens ceiling.** In F.19-pre, all thinking cells hit
  the `max_completion_tokens=4096` ceiling on Prompt 3. c08 was the
  only planner to emit any P3 content, and even it truncated mid-list.
  Options for F.19:
  - Bump planner budget to **8192**. Simple; costs a bit more latency;
    likely lets c08 finish and might promote c05/c06 as faster planner
    candidates (they scored 37/38 on P1+P2 before P3 truncation).
  - Keep 4096 and accept partial plans, streaming to UI. Cheaper
    latency-wise but weaker for the plan-generation use case.
  - **Recommendation:** bump to 8192 for planner role only, keep 2048
    for coder. Confirm with re-bench of c05/c06 before making 8192 the
    permanent default.
- **BFF port reconciliation.** Forge-OH BFF is on :8081. The
  `colossus-ops` skill lists BFF on :8000. Not blocking F.19, but
  should be sorted before UI wiring lands.
- **VRAM headroom for two models.** qwen3.5-nvfp4 and
  qwen3-thinking-2507-awq don't both fit in 30 GiB simultaneously. F.19
  needs a swap-on-demand strategy (see item 2 above).

## Exact next action
Read `bff/services/model_router.py` to inventory current routes and
health-check surfaces:

```bash
cd ~/dev/forge-oh
grep -n 'route_request\|health_check\|VLLM_\|OLLAMA_\|def [a-z]' bff/services/model_router.py | head -40
grep -n 'MODEL_ROUTE\|BACKEND\|coder\|planner' bff/services/model_router.py | head -40
```

Then draft the F.19 wiring plan: exact commit sequence, new env vars
(`LLM_CODER_MODEL`, `LLM_PLANNER_MODEL`, `LLM_CODER_URL`,
`LLM_PLANNER_URL` if we go dual-port), test cases, and swap-strategy
ADR if the supervisor script gets non-trivial.

## Key files/refs
- **ADR-009:** `docs/adr/009-local-llm-selection.md`
- **Scores:** `bench/f19pre/results/scores_20260803.md`
- **Packed answers:** `bench/f19pre/results/bench_f19pre_20260803_175759.md`
- **Raw JSON:** `bench/f19pre/results/raw/20260803_170129_run/`
- **Launchers used in F.19-pre:** `bench/f19pre/vllm_launch.sh` (and
  Ollama helpers alongside).
- Commits this session: pack `4c25051`; ADR + scores + logs commit
  follows (see push output).
