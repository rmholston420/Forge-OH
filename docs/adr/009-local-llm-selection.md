# ADR-009: Local LLM Selection for Forge-OH F.19+ (Coder + Planner Roles)

- **Status:** Accepted
- **Date:** 2026-08-03
- **Slice:** F.19-pre (path-D v2 blocker) — Forge-OH-Action-Plan-v4
- **Related:** [BUILD_LOG.md](../../BUILD_LOG.md), [PORTING_LEDGER.md](../../PORTING_LEDGER.md); supersedes the F.15 default of `qwen3-coder:30b` + `qwen3.6:35b-a3b` on Ollama for the two-role router.
- **Note on numbering:** The F.19-pre plan initially referred to this decision as "ADR-0007", but `007-verify-loop.md` already exists. Numbering resumes at 009.

## Context

Before F.19, the Coder/Planner router in `bff/services/model_router.py`
targeted `qwen3-coder:30b` (Q4_K_M) and `qwen3.6:35b-a3b` (Q4_K_M) via
Ollama on Colossus (Kubuntu, single RTX 5090 Blackwell SM_120, 32 GiB
VRAM, 128 GiB RAM). Two problems drove F.19-pre:

1. Ollama has no reliable per-request `enable_thinking=false` toggle for
   qwen3.5-MoE models. The `chat_template_kwargs` extra_body pathway is
   silently dropped, so the "fast non-thinking" Coder path on qwen3.5-MoE
   collapses into a full reasoning trace that burns the entire
   `max_completion_tokens` budget and returns `_(empty content)_`.
2. It was unclear whether vLLM's Blackwell (SM_120) support was stable
   enough on this GPU to switch the default runtime off Ollama.

F.19-pre answered both by running an 8-cell bench (2 roles × 2 runtimes ×
2 models) with three Forge-OH-native prompts (RBAC ImportError, duplicate
resolution, Step-3 vertical slice plan).

## Evidence

Full bench harness, raw JSON, packed markdown, and per-answer scoring:

- `bench/f19pre/results/raw/20260803_170129_run/*.json`
- `bench/f19pre/results/bench_f19pre_20260803_175759.md`
- `bench/f19pre/results/scores_20260803.md` (this ADR's scoring, added
  in the same commit)

Aggregate totals (max 120 = 3 prompts × 40 points):

| Cell | Runtime | Model | Role | Total |
|------|---------|-------|------|-------|
| c04 | vLLM | qwen3.5-nvfp4 | Coder | **109** |
| c01 | Ollama | qwen3-coder:30b | Coder | 96 |
| c02 | vLLM | qwen3-coder-30b-awq | Coder | 93 |
| c03 | Ollama | qwen3.5:35b-a3b think:false | Coder | **0 (BROKEN)** |
| c05 | Ollama | qwen3.5:35b-a3b think:true | Planner | 80 |
| c06 | vLLM | qwen3.5-nvfp4 think:true | Planner | 80 |
| c07 | Ollama | qwen3-thinking-2507:q4kxl | Planner | 64 |
| c08 | vLLM | qwen3-thinking-2507-awq | Planner | **87** |

## Decision

### 1. Coder role → `qwen3.5-nvfp4` via vLLM (c04)

Route Coder traffic (fast-path code edits, one-shot bash generation,
minimal-diff refactors) to **qwen3.5-nvfp4** served by vLLM.

Reasoning:

- c04 was the only Coder cell that caught **both** the failing import
  and the `@require_role` decorator usage in the RBAC ImportError
  prompt. c01/c02 emit `sed '12d'` line-number deletes that leave the
  decorator and produce a `NameError` at runtime.
- c04 was the only cell across all 8 that produced a **complete
  10-commit atomic plan** for the Step-3 vertical slice (P3).
- c04 also had the highest tok/s among 35B cells (260-267 med) and
  sub-3s latency across all three prompts.
- c03 (the Ollama equivalent path with `think:false`) returned empty
  content on all three prompts — see §4.

### 2. Planner role → `qwen3-thinking-2507-awq` via vLLM (c08)

Route Planner traffic (multi-step commit sequences, architectural
justification, ordered refactor plans) to **qwen3-thinking-2507-awq**
served by vLLM.

Reasoning:

- c08 is the **only planner cell that emitted a partially-consumable
  P3 output** — every other thinking cell (c05, c06, c07) hit the
  `max_completion_tokens=4096` ceiling mid-reasoning and returned
  empty final content.
- c08 tied for top on P2 (38/40) with c05 and c06, so no quality
  regression on the shorter architectural prompt.
- c08 is slow (117-166 tok/s, 16-24s median latency). This is
  acceptable because the Planner role is invoked less frequently than
  Coder and its outputs are structured commit sequences, not
  interactive edits.

### 3. Runtime = vLLM for both roles

Both selected cells run on vLLM. The Ollama runtime is retired as the
default backend for both roles. Ollama remains available in
`bff/services/model_router.py` as a fallback endpoint but is no longer
the primary route. This is driven by §4 more than by raw speed.

### 4. Retire qwen3.5-MoE from the non-thinking Coder path

The Ollama `enable_thinking=false` toggle for qwen3.5-MoE is a no-op
under the current Ollama build. This makes the `qwen3.5:35b-a3b
think:false` configuration a **user-visible bug**: the model appears
to accept the flag, silently ignores it, burns the whole token
budget on chain-of-thought, and returns nothing. vLLM's
`chat_template_kwargs` support is verified working on qwen3.5-nvfp4
(cell c04), so the qwen3.5-MoE architecture is retained for use as a
Planner (§2 supersedes this at the routing layer, but the vLLM
launcher for qwen3.5-nvfp4 stays deployable).

### 5. vLLM Blackwell (SM_120) operational notes

Captured for future launchers, and appended to `DEBUG_LOG.md` under
2026-08-03:

- vLLM **v0.10.2** does not recognize the `qwen3_5_moe` architecture.
  Upgrade to **v0.26.0** or later (`vllm/vllm-openai:latest` as of
  2026-08-03, image digest
  `ffd46bfab2128bb84146050e98b51a617c6575ab`).
- qwen3.5-MoE is a **hybrid Mamba/attention** model. On a single
  RTX 5090 with `--gpu-memory-utilization 0.90` you must pass
  `--max-num-seqs 128` (or ≤255) or engine-init aborts with
  `max_num_seqs (256) exceeds available Mamba cache blocks (255)`.
- HuggingFace repos advertising a specific quant format (AWQ,
  ModelOpt-FP4, etc.) frequently ship as **compressed-tensors** under
  the hood. Do **not** set `--quantization` explicitly for c02/c04/c08
  weights; let vLLM autodetect from
  `config.json.quantization_config.format`.
- Usable Blackwell VRAM budget for a single-tenant server is ~30 GiB
  (90% util → 28.25 GiB for weights+cache+activations).

## Consequences

**Positive:**

- Coder answers now include decorator handling and full-length atomic
  plans without hitting non-thinking token ceilings.
- The Ollama `think:false` silent-failure mode is removed from the
  default route.
- Both roles land on a single runtime (vLLM), simplifying the
  `model_router.py` health-check surface.

**Negative:**

- vLLM cold-start on Colossus is heavier than Ollama's (Docker image
  pull + weight load, ~30-60s). The launcher scripts under
  `bench/f19pre/vllm_launch.sh` are the reference for boot flags; the
  operational launcher for F.19 should live under `ops/` (F.19 work).
- Planner latency (c08) is 16-24s per response. If interactive
  planning UX requires <10s, we should re-run the bench with
  `max_completion_tokens=8192` and re-evaluate c05/c06 as faster
  candidates (both scored 37/38 on P1+P2 before length-truncating on
  P3 at 4096).
- Slow-Planner throughput may bottleneck any batch workflow that
  fans out multiple planner calls. Mitigation: enqueue planner work
  and stream progress; do not block coder work on planner completion.

## Follow-ups (out of scope for F.19-pre)

1. Re-bench c05/c06/c07 with `max_completion_tokens=8192` to see if
   any thinking cell dominates c08 on P3.
2. Ollama upstream tracking: watch for a fix to
   `chat_template_kwargs.enable_thinking` for qwen3.5-MoE. If
   corrected, revisit c03 as a fast-Coder candidate.
3. Reconcile BFF port assignment (Forge-OH BFF was on 8000; the
   `colossus-ops` skill lists 8081). Not blocking, but should be
   settled before F.19 UI wiring.

---

_Bench methodology, per-prompt scoring, and length-ceiling forensics
in `bench/f19pre/results/scores_20260803.md`._
