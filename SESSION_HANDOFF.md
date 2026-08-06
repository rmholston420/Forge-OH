# Forge-OH Session Handoff — 2026-08-06 15:24 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 8 · Slice 8.0 (vLLM serving-infra config bundle)
- **Plugin / kernel component:** coder role · vLLM launcher · Docker path (canonical per ADR-013 amendment #1)
- **Ports / adapters in progress:**
  - `ops/vllm_launch_coder.sh` (canonical coder launcher, :8501, `vllm/vllm-openai:latest`, `qwen3.6-27b-int4-autoround`)
  - `bff/services/agent_compose.py` (new file, ~20 LoC, APC-block-alignment helper for condenser `keep_first`)

## Completed this session

- Read `docs/reconciliation-plan-v1.md`, Council-Synthesis §8.0 slice contract, KNOWN_ISSUES §68, `bench/pathE_qwen36_27b/vllm_launch.sh:195`, DEBUG_LOG 2026-08-03 18:34 EDT.
- Drafted `docs/reconciliation-plan-stage-8.md` §8.0 targeting `scripts/vllm_start.sh` (F.18 GGUF experiment) — pushed as commit `b0dd4a0`.
- User ran the Colossus-side vLLM version probe. Two findings:
  1. `~/venv/vllm-new/bin/vllm --version` failed with `ImportError: huggingface-hub>=0.34.0,<1.0 is required ... found huggingface-hub==1.26.0`. The native venv is broken but not on any live Slice 8.0 path.
  2. This forced the recognition that the canonical Forge-OH launcher is `ops/vllm_launch_coder.sh` (Docker, int4-AutoRound), not `scripts/vllm_start.sh` (F.18 GGUF experiment).
- Fully rewrote `docs/reconciliation-plan-stage-8.md` §8.0 to target the correct launcher. Redid VRAM math against F.3 baseline peak (32,599 MiB) and F.3.0 concurrency=1. Filed KNOWN_ISSUES entry for the venv breakage.

## Remaining before Slice 8.0 Definition of Done

1. Verify vLLM version inside `vllm/vllm-openai:latest` on Colossus (see §Exact next action). Nearly certain ≥ 0.10; §8.0 doc §Open questions Q1 tracks this.
2. Agent writes the 4-flag block + 2 modified flags into `ops/vllm_launch_coder.sh` (see `docs/reconciliation-plan-stage-8.md` §Flag matrix `Slice 8.0 target flags`). One commit.
3. Agent adds `bff/services/agent_compose.py` (helper) + one call site in whatever composes the Forge-OH agent (locate at execution time — likely `bff/main.py` or `bff/services/agent_factory.py`). Same commit.
4. User restarts coder container: `ops/vllm_supervisor.sh down coder && ops/vllm_supervisor.sh up coder`. Confirms `/v1/models` responds.
5. User re-runs `bench/pathF_swebench/` smoke-30 at `--concurrency 1` against the same 30 tasks that produced Path A pass@1 = 33.3% baseline at `~/.forge-oh/bench_pathF_swebench/20260806_1211_run/`.
6. DoD attestation:
   - Regression ≤ 1 task vs. 33.3% baseline. Rollback bisect (§Rollback strategy in the doc) if worse.
   - 4 context-budget-skipped tasks (`django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248`) load through the model (pass or fail, but not `context-budget-skip`).
7. Agent appends BUILD_LOG entry + overwrites SESSION_HANDOFF pointing to §8.0b (planner-side copy). Commits + pushes.

## Open questions / awaiting user answer

None blocking. Three non-blocking questions surfaced in the doc (§Open questions Q1/Q2/Q3): vLLM version confirmation, n-gram acceptance rate on the coder model, and vLLM `--block-size` default. Q1 resolves with the exact-next-action probe below.

## Exact next action

Paste on Colossus:

```bash
cd ~/dev/forge-oh && git pull && \
  docker run --rm vllm/vllm-openai:latest --version 2>&1 | head -5
```

Return the version string. On confirming ≥ 0.10:

- I write the full 4-flag addition + 2 modified flags into `ops/vllm_launch_coder.sh` (exactly matching `docs/reconciliation-plan-stage-8.md` §Flag matrix "Slice 8.0 target flags").
- I add `bff/services/agent_compose.py` (~20 LoC helper) and wire it into the agent composition site (I locate it before editing).
- I commit both under one commit: "Slice 8.0: vLLM coder-role serving-infra config bundle".
- I hand back with the exact restart + smoke-30 commands.

If < 0.10 (very unlikely given F.19.5 tracking): degraded version — drop `--long-prefill-token-threshold`; use pre-0.10 spec-decode syntax.
