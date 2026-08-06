# Forge-OH Reconciliation Plan — Stage 8 Companion

**Status:** DRAFT (2026-08-06) — Slice 8.0 kickoff. Only §8.0 is drafted here; §8.0.5–§8.9 are placeholders that inherit from `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (Perplexity project files repo, commit `8e093bc`) and [ADR-029](./adr/029-sdk-native-adoption-for-stage-8.md).

**Canonical governance:** ADR-028 (Stage 7 deviation, capability slices renumbered to Stage 8) and ADR-029 (SDK-native adoption per slice).

---

## §8.0 — vLLM serving-infra config bundle

### Scope (verbatim from Council-Synthesis §8.0, line 116)

> Enable APC + spec-decode + fp8 KV-cache + chunked prefill; align OpenHands condenser `keep_first` with APC prefix; re-baseline smoke-30.
>
> **Sizing:** 1 slice (config only). **Depends on:** — (independent). **Formerly:** 7.0.

### Definition of Done

1. `scripts/vllm_start.sh` launches the current baseline model (`qwen3-coder-30b` GGUF) with the full flag bundle in §Flag matrix below, on port :8500, on Colossus, one nohup restart.
2. `curl -s http://127.0.0.1:8500/v1/models` returns the served model within 900s of restart.
3. `bench/pathF_swebench/` smoke-30 (the same 30 tasks that produced Path A pass@1 = 33.3% baseline at `~/.forge-oh/bench_pathF_swebench/20260806_1211_run/`) re-runs against the reconfigured launcher.
4. Smoke-30 does not regress by more than **1 task** vs. the 33.3% baseline (10/30 tasks solved). Any regression greater than 1 task blocks the slice and forces the fallback strategy in §Rollback.
5. The 4 context-budget-skipped tasks from KNOWN_ISSUES §68 (`django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248`) no longer skip — they load and either pass or fail through the model, not through the harness's `context-budget-skip` short-circuit.
6. **Condenser `keep_first` alignment** — `LLMSummarizingCondenser` config in whatever composes the Forge-OH agent (see [ADR-029 §D4](./adr/029-sdk-native-adoption-for-stage-8.md)) is set so its preserved prefix aligns with the vLLM APC prefix boundary. Concretely: `keep_first` events must render to a token count that is a multiple of the vLLM APC block size (see §Condenser alignment below).
7. BUILD_LOG entry timestamped at slice completion, and SESSION_HANDOFF overwritten. No PORTING_LEDGER entry — this slice adopts SDK primitives already vendored and adds no new OSS.

### Stop condition (stricter than DoD, per ADR-028)

Slice 8.0 stops the moment DoD item 4 (regression ≤ 1 task) can be attested. It does **not** wait for §8.0.5's 100-task expanded smoke or paired McNemar — those are §8.0.5's contract. Slice 8.0 also does not attempt to raise pass@1; it is a zero-code slice whose only success criterion is "no regression + context ceiling raised."

### Flag matrix (proposed)

Baseline for comparison is the current `scripts/vllm_start.sh` at commit `f5eff7b` (see §Baseline flags below).

| Flag | Current | Slice 8.0 target | Rationale |
|---|---|---|---|
| `--enable-prefix-caching` | ON | **ON (unchanged)** | APC already enabled. Slice 8.0 does not change this; it aligns the condenser to it (DoD item 6). |
| `--kv-cache-dtype` | (default `auto` → fp16) | **`fp8`** | Halves KV memory per token. Confirmed working on Colossus SM_120 with AWQ models via `bench/pathE_qwen36_27b/vllm_launch.sh:195`. Enables DoD item 5 (raise ceiling without OOM). |
| `--max-model-len` | 32768 | **65536** | Council-Synthesis §8.0 targets the 4/30 context-budget-skipped tasks. All four (matplotlib, sympy, sphinx, django) fit in 65k with 4k output reserve. 131072 (native) would force `--max-num-seqs` reduction and courts long-context regressions §8.0 warns about. |
| `--max-num-seqs` | 8 | **8 (unchanged)** | 65k×fp8-KV × 8 seqs ≈ 12.5 GiB KV budget, fits in the ~13 GiB headroom left after 18.5 GiB weights + 0.5 GiB compile. Confirmed by DEBUG_LOG §2026-08-05 02:31 "AWQ/GPTQ 4-bit: usable up to ~32-35B params." Same 8 preserves throughput profile of the baseline. |
| `--enable-chunked-prefill` | OFF (default varies by vLLM version) | **ON (explicit)** | Council-Synthesis §8.0 direct requirement. Makes long-prompt scheduling coexist cleanly with decode requests. Pairs with `--long-prefill-token-threshold` below. |
| `--long-prefill-token-threshold` | (unset → default) | **`4096`** | Council-Synthesis line 66 (Gemini) recommends this as the direct fix for context-ceiling pressure. Prompts longer than 4096 tokens are chunked instead of one-shot prefilled; keeps decode latency responsive while ceiling is raised to 65k. |
| `--speculative-config` | OFF | **`'{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":4}'`** | n-gram spec-decode. Zero extra VRAM. Council-Synthesis rates "modest but stacks." Model-based draft deferred — its VRAM cost cannibalizes the fp8-KV win. |
| `--dtype float16` | ON (GGUF-required) | **ON (unchanged)** | GGUF loader rejects bf16 on SM_120. Not a Slice 8.0 concern. |
| `--gpu-memory-utilization` | 0.85 | **0.90** | Matches `bench/pathE_qwen36_27b/vllm_launch.sh:191`. Raises effective VRAM budget from 27.2 GiB to 28.8 GiB — the extra ~1.6 GiB is what makes the 65k×8-seq×fp8 KV envelope feasible. |
| `--served-model-name` | `qwen3-coder-30b` | **`qwen3-coder-30b` (unchanged)** | Do not change; BFF model-router (`bff/services/model_router.py`) resolves by served name. |
| `--host` / `--port` | `127.0.0.1:8500` | **unchanged** | Single-port baseline; coder+planner split deferred out of Slice 8.0. |
| `--hf-config-path Qwen/Qwen3-Coder-30B-A3B-Instruct` | ON | **ON (unchanged)** | GGUF has no tokenizer config; this is required. |
| `VLLM_USE_FLASHINFER_SAMPLER=0` (env) | ON | **ON (unchanged)** | SM_120 workaround. |
| `VLLM_ATTENTION_BACKEND=FLASH_ATTN` (env) | ON | **ON (unchanged)** | Required for SM_120. |

**Baseline flags** (current `scripts/vllm_start.sh` line 46–55 verbatim):

```bash
"$VENV_BIN" serve "$BLOB" \
  --served-model-name "$SERVED_NAME" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --gpu-memory-utilization 0.85 \
  --max-model-len 32768 \
  --max-num-seqs 8 \
  --dtype float16 \
  --enable-prefix-caching \
  --hf-config-path Qwen/Qwen3-Coder-30B-A3B-Instruct
```

**Slice 8.0 target flags** (proposed replacement for the same block):

```bash
"$VENV_BIN" serve "$BLOB" \
  --served-model-name "$SERVED_NAME" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --gpu-memory-utilization 0.90 \
  --max-model-len 65536 \
  --max-num-seqs 8 \
  --dtype float16 \
  --enable-prefix-caching \
  --kv-cache-dtype fp8 \
  --enable-chunked-prefill \
  --long-prefill-token-threshold 4096 \
  --speculative-config '{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":4}' \
  --hf-config-path Qwen/Qwen3-Coder-30B-A3B-Instruct
```

**Net change**: 5 flags added (`--kv-cache-dtype fp8`, `--enable-chunked-prefill`, `--long-prefill-token-threshold 4096`, `--speculative-config …`), 2 flags modified (`--gpu-memory-utilization 0.85 → 0.90`, `--max-model-len 32768 → 65536`), 0 flags removed. Zero code change outside `scripts/vllm_start.sh`.

### VRAM budget math (for DoD item 4 confidence)

- Total VRAM: 32.0 GiB (RTX 5090)
- `gpu-memory-utilization=0.90`: usable = **28.8 GiB**
- GGUF model weights (qwen3-coder-30b, Q4_K_M-class): ~**18.5 GiB**
- torch.compile / inductor allocations: ~**0.5 GiB**
- Reserved after weights + compile: **28.8 − 18.5 − 0.5 = 9.8 GiB for KV**
- fp8 KV cost @ 65536 ctx × 8 seqs (Qwen3-Coder-30B-A3B, 48 layers, 8 KV heads × 128 head_dim):
  - Per-token KV bytes ≈ 2 × layers × kv_heads × head_dim × sizeof(fp8) = 2 × 48 × 8 × 128 × 1 = **98,304 B ≈ 96 KiB**
  - Per-seq KV @ 65536 ctx ≈ 96 KiB × 65536 = **6.0 GiB**
  - 8 seqs × 6.0 GiB = **48 GiB → exceeds 9.8 GiB**

**This math shows the naive expansion doesn't fit.** vLLM's KV cache is not per-seq × ctx, it's a shared paged allocator (block size default 16 tokens). Effective KV need at steady state ≈ `avg_ctx_per_seq × num_seqs × per_token_kv`. On smoke-30 the avg prompt is ~12k tokens; steady-state KV therefore ≈ 96 KiB × 12,288 × 8 = **9.0 GiB**, which fits inside the 9.8 GiB envelope with ~0.8 GiB headroom.

**Peak KV** happens if all 8 concurrent sequences hit near-65k prompts simultaneously. This is extremely unlikely on smoke-30 (only 4/30 tasks exceed 32k), but if it happens vLLM will admission-control (queue instead of OOM) via its paged allocator — the effective behavior is "occasional preemption," not "crash." §8.0.5 will collect the numbers needed to prove or refute this in production.

**Contingency:** if the smoke-30 run hits repeated preemption, `--max-num-seqs 4` (halve concurrency) recovers throughput per seq at the cost of parallelism. This is the fallback in §Rollback item 2.

### Condenser alignment (DoD item 6)

Per [ADR-029 §D4](./adr/029-sdk-native-adoption-for-stage-8.md), `LLMSummarizingCondenser` gets composed into the Forge-OH agent stack (a compose-time change, not a slice on its own). The `keep_first` field must preserve enough events at the head of the conversation to cover the vLLM APC-cached prefix.

vLLM APC caches at block granularity. **APC block size default is 16 tokens** (`--block-size 16`). The condenser's "kept events" render to a prompt block via `to_prompt`; that block's token length is what must be a multiple of 16 to align cleanly.

**Practical setting for Slice 8.0**:
- The system prompt + task descriptor in Forge-OH's agent typically renders to ~1200 tokens (measured in `bench/pathF_swebench/` prompts).
- `keep_first=4` (Council-Synthesis line 60 recommendation) preserves the first 4 events, which for Forge-OH's event schema is: `SystemPromptEvent`, `UserTaskEvent`, `RepoManifestEvent`, `PlanEvent`. Token count for this quadruple: measure at composition time, pad the `to_prompt` block with a trailing `\n` line to the next multiple of 16.
- **Concrete value**: `keep_first=4` proposed. Alignment enforced at compose time via a helper (`bff/services/agent_compose.py::pad_prefix_to_apc_block` — a new one-function file, ≤ 20 LoC).

If measurement in §8.0.5 shows the 4-event prefix routinely varies in token count across tasks, we bump `keep_first` to 8 (still well within `LLMSummarizingCondenser`'s validated defaults).

### Rollback strategy (if DoD item 4 fails)

If the smoke-30 re-baseline regresses by more than 1 task:

1. **Bisect the flag additions** (in this order): remove `--speculative-config` first (least tested; workload-dependent per Council-Synthesis). Re-run smoke. If pass, spec-decode alone caused the regression — file a follow-up to investigate acceptance rate.
2. **If still regressed**: remove `--enable-chunked-prefill` + `--long-prefill-token-threshold`. Re-run.
3. **If still regressed**: lower `--max-model-len` back to 32768 (isolates fp8 KV as the change). Re-run. If pass, the fp8 kernel has a long-context regression on GGUF + SM_120; file a DEBUG_LOG entry and defer the ceiling raise to a subsequent slice.
4. **If still regressed**: revert `--kv-cache-dtype fp8`. Re-run. If pass, fp8 KV on GGUF float16 is not viable on this stack; note the finding and revisit at AWQ migration.
5. **Final fallback**: revert `scripts/vllm_start.sh` to the exact `f5eff7b` state and file the failure as an ADR-worthy blocker.

Each rollback step is one commit. The bisect finishes in one bench run per step.

### Files touched (Slice 8.0)

1. `scripts/vllm_start.sh` — replace flag block (see §Flag matrix above).
2. `bff/services/agent_compose.py` (new, ~20 LoC) — the APC-block-alignment helper for condenser `keep_first`.
3. `bff/main.py` or wherever the agent is composed — one call to the helper.
4. `docs/reconciliation-plan-stage-8.md` (this file) — mark §8.0 status → **Ratified** when smoke-30 passes.
5. `BUILD_LOG.md` — append slice-completion entry.
6. `SESSION_HANDOFF.md` — overwrite to point to Slice 8.0.5.

### Open questions surfaced during draft (NON-BLOCKING for Slice 8.0 execution)

**Q1: Exact vLLM version pinned.** `scripts/vllm_start.sh` uses `$HOME/venv/vllm-new/bin/vllm` without a version pin. `--long-prefill-token-threshold` requires vLLM ≥ 0.10.0. Before executing Slice 8.0, run `~/venv/vllm-new/bin/vllm --version` on Colossus and confirm ≥ 0.10.0. If not, either upgrade (out-of-scope) or drop the `--long-prefill-token-threshold` line (keeps `--enable-chunked-prefill` with default threshold).

**Q2: `--speculative-config` JSON syntax.** vLLM ≥ 0.10 accepts inline JSON on the command line via `--speculative-config`. Older versions used `--num-speculative-tokens` + `--speculative-model`. Q1's version check answers this simultaneously.

**Q3: APC block size default.** The 16-token default is what vLLM ships; `--block-size` can be overridden. Slice 8.0 does not touch `--block-size`; §8.0.5's measurement work will confirm the block size in effect and refine `keep_first` if needed.

Neither Q1 nor Q2 nor Q3 blocks the drafting of Slice 8.0. All three are execution-time checks the operator does on Colossus in a single shell probe. If Q1 returns < 0.10.0, the flag matrix degrades gracefully to a 3-flag bundle (fp8 KV + APC + n-gram spec-decode via old syntax) which is still Council-Synthesis §8.0's minimum viable bundle.

---

## §8.0.5 through §8.9 — Placeholders

Not drafted in this file. Inherit from:

- `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (Perplexity project files repo, commit `8e093bc`) for slice contracts, dependency order, and sizing.
- [ADR-029](./adr/029-sdk-native-adoption-for-stage-8.md) §D1–§D5 for adoption-vs-hand-build decisions per slice.

To be drafted at each slice's kickoff, following the pattern of §8.0 above.
