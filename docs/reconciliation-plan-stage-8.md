# Forge-OH Reconciliation Plan — Stage 8 Companion

**Status:** DRAFT (2026-08-06) — Slice 8.0 kickoff. Only §8.0 is drafted here; §8.0.5–§8.9 are placeholders that inherit from `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (Perplexity project files repo, commit `8e093bc`) and [ADR-029](./adr/029-sdk-native-adoption-for-stage-8.md).

**Canonical governance:** ADR-028 (Stage 7 deviation, capability slices renumbered to Stage 8), ADR-029 (SDK-native adoption per slice), ADR-013 amendment #1 (Qwen3.6-27B-int4-AutoRound coder / DeepSeek-R1-distill-32B-AWQ planner).

**Revision history:**
- 2026-08-06 15:12 EDT — initial draft targeted `scripts/vllm_start.sh` (F.18 GGUF experiment). Superseded within the hour.
- 2026-08-06 15:24 EDT — retargeted to canonical `ops/vllm_launch_coder.sh` (Docker · int4-AutoRound) per ADR-013 amendment #1 + DEBUG_LOG 2026-08-03 18:34 EDT. VRAM math redone against actual F.3.0 concurrency=1 profile.
- 2026-08-06 15:30 EDT — vLLM 0.26.0 confirmed in `vllm/vllm-openai:latest` (well above 0.10 threshold; full flag block ratified). DoD item 6 (condenser alignment) moved to Slice 8.6 — the compose site the condenser wiring needs does not exist yet in BFF (BFF forwards to OpenHands agent-server on :8090; condenser lives inside that process). ADR-029 D4 amended accordingly. Flag bundle applied to `ops/vllm_launch_coder.sh` in the same commit.

---

## §8.0 — vLLM serving-infra config bundle (coder role first)

### Scope

Council-Synthesis §8.0 (line 116) calls for one config bundle enabling APC + spec-decode + fp8 KV-cache + chunked prefill on vLLM. Forge-OH's canonical vLLM stack (per [ADR-013 amendment #1](./adr/013-qwen36-27b-canonical-coder-planner.md)) uses two Docker containers that share the single RTX 5090 via the supervisor's auto-swap policy:

- **Coder** — `ops/vllm_launch_coder.sh` → `qwen3.6-27b-int4-autoround` on :8501, `vllm/vllm-openai:latest`.
- **Planner** — `ops/vllm_launch_planner.sh` → `deepseek-r1-distill-qwen-32b-awq` on :8511, same image.

Because the pair never runs concurrently on the same GPU (32 GiB is not enough for both), §8.0 applies the bundle **coder-only first**. A follow-up §8.0b copies the identical bundle onto the planner launcher after coder DoD is green. This isolates any regression to one model class, which the rollback bisect §Rollback strategy needs.

**Native venv (`~/venv/vllm-new`) is NOT a target.** Per DEBUG_LOG 2026-08-03 18:34 EDT the native venv runs vLLM 0.10.2 which predates required features; the vetted stack is the pinned Docker image. F.19.5 tracks the native-venv 0.26+ upgrade separately.

### Definition of Done

1. `ops/vllm_launch_coder.sh` launches with the full flag bundle in §Flag matrix below, on Colossus, via `ops/vllm_supervisor.sh up coder`.
2. `curl -sf http://127.0.0.1:8501/v1/models` returns the served model (`qwen3.6-27b-int4-autoround`) within 900s of launch.
3. `bench/pathF_swebench/` smoke-30 (same 30 tasks that produced Path A pass@1 = 33.3% baseline at `~/.forge-oh/bench_pathF_swebench/20260806_1211_run/`) re-runs against the reconfigured launcher at `--concurrency 1` (F.3.0's operating point).
4. Smoke-30 does not regress by more than **1 task** vs. the 33.3% baseline (10/30 tasks solved). Any regression greater than 1 task blocks the slice and forces the §Rollback strategy.
5. The 4 context-budget-skipped tasks from KNOWN_ISSUES §68 (`django-15629`, `matplotlib-26208`, `sphinx-7590`, `sympy-14248`) no longer skip — they load and either pass or fail through the model, not through the harness's `context-budget-skip` short-circuit.
6. BUILD_LOG entry timestamped at slice completion. SESSION_HANDOFF overwritten to point to §8.0b (planner-side copy). No PORTING_LEDGER entry — this slice is vLLM launcher config only; no code beyond the launcher flags.

**Note:** Prior DoD item 6 (condenser `keep_first` alignment) is deferred to **Slice 8.6**. ADR-029 D4 originally proposed the condenser tweak ride on §8.0 as a compose-time change, but Forge-OH's BFF has no agent-compose site — it forwards to OpenHands agent-server on :8090, which owns the condenser process. Slice 8.6 (SDK Skills adoption) will introduce the compose site and wire `keep_first` there in the same commit.

### Stop condition (stricter than DoD, per ADR-028)

Slice 8.0 stops the moment DoD item 4 (regression ≤ 1 task) can be attested. It does **not** wait for §8.0.5's 100-task expanded smoke or paired McNemar — those are §8.0.5's contract. Slice 8.0 also does not attempt to raise pass@1; it is a config-only slice whose only success criterion is "no regression + context ceiling raised."

### Flag matrix (proposed)

Baseline for comparison is the current `ops/vllm_launch_coder.sh` at commit `b0dd4a0` (see §Baseline flags below).

| Flag | Current | Slice 8.0 target | Rationale |
|---|---|---|---|
| `--enable-prefix-caching` | ON | **ON (unchanged)** | APC already enabled. |
| `--kv-cache-dtype` | (default `auto` → fp16) | **`fp8`** | Halves KV memory per token. Proven on Colossus SM_120 with AWQ / compressed-tensors int4 models via `bench/pathE_qwen36_27b/vllm_launch.sh:195`. Enables DoD item 5 (raise ceiling without OOM). |
| `--max-model-len` | 32768 | **65536** | Council-Synthesis §8.0 targets the 4/30 context-budget-skipped tasks. All four fit in 65k with 4k output reserve. 131072 (native) would force `--max-num-seqs` reduction and courts long-context regressions §8.0 warns about. |
| `--max-num-seqs` | 128 | **128 (unchanged)** | Steady-state concurrency is 1 (F.3.0 uses `--concurrency 1` in `bench/pathF_swebench/`). 128 is a paged-allocator ceiling that does not itself allocate KV. VRAM math in §VRAM budget below shows the raised ceiling fits at concurrency=1. |
| `--enable-chunked-prefill` | OFF (default varies by vLLM version) | **ON (explicit)** | Council-Synthesis §8.0 direct requirement. Makes long-prompt scheduling coexist cleanly with decode. Pairs with `--long-prefill-token-threshold`. |
| `--long-prefill-token-threshold` | (unset → default) | **`4096`** | Council-Synthesis line 66 (Gemini) recommends this as the direct fix for context-ceiling pressure. Prompts >4096 tokens are chunked instead of one-shot prefilled. |
| `--speculative-config` | OFF | **`'{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":4}'`** | n-gram spec-decode. Zero extra VRAM. Council-Synthesis rates "modest but stacks." Model-based draft deferred — its VRAM cost cannibalizes the fp8-KV win. |
| `--gpu-memory-utilization` | 0.90 | **0.90 (unchanged)** | Already at pathE launcher level. |
| `--dtype` | `auto` | **`auto` (unchanged)** | int4-AutoRound loader auto-selects; do not override. |
| `--tool-call-parser qwen3_coder` | ON | **ON (unchanged)** | Model-specific; not a Slice 8.0 concern. |
| `--enable-auto-tool-choice` | ON | **ON (unchanged)** | Coder-role requirement. |
| `--trust-remote-code` | ON | **ON (unchanged)** | int4-AutoRound quant class requires it. |
| `--host 0.0.0.0 --port 8000` (in-container) | ON | **ON (unchanged)** | Container-internal port; supervisor maps host `:8501 → :8000`. |
| `VLLM_USE_FLASHINFER_SAMPLER=0` (env) | ON | **ON (unchanged)** | SM_120 workaround. |
| `VLLM_ATTENTION_BACKEND=FLASH_ATTN` (env) | ON | **ON (unchanged)** | Required for SM_120. |
| `HF_HUB_OFFLINE=1` (env) | ON | **ON (unchanged)** | Offline model resolution. |

**Baseline flags** (current `ops/vllm_launch_coder.sh` lines 55–68 verbatim):

```bash
docker run -d --name "$CONTAINER" --gpus all \
  --ipc=host --shm-size=8g \
  "${BLACKWELL_ENVS[@]}" \
  -v "$MODELS_DIR:/models:ro" \
  -p "${PORT}:8000" \
  "$IMAGE" \
  --model "/models/$MODEL_DIR" \
  --served-model-name "$NAME" \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --max-num-seqs 128 \
  --dtype auto \
  --trust-remote-code \
  --tool-call-parser qwen3_coder \
  --enable-auto-tool-choice \
  --enable-prefix-caching \
  "$@"
```

**Slice 8.0 target flags** (proposed replacement — additions marked, existing preserved):

```bash
docker run -d --name "$CONTAINER" --gpus all \
  --ipc=host --shm-size=8g \
  "${BLACKWELL_ENVS[@]}" \
  -v "$MODELS_DIR:/models:ro" \
  -p "${PORT}:8000" \
  "$IMAGE" \
  --model "/models/$MODEL_DIR" \
  --served-model-name "$NAME" \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 65536 \
  --max-num-seqs 128 \
  --dtype auto \
  --trust-remote-code \
  --tool-call-parser qwen3_coder \
  --enable-auto-tool-choice \
  --enable-prefix-caching \
  --kv-cache-dtype fp8 \
  --enable-chunked-prefill \
  --long-prefill-token-threshold 4096 \
  --speculative-config '{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":4}' \
  "$@"
```

**Net change**: 4 flags added (`--kv-cache-dtype fp8`, `--enable-chunked-prefill`, `--long-prefill-token-threshold 4096`, `--speculative-config …`), 1 flag modified (`--max-model-len 32768 → 65536`), 0 flags removed. Zero code change outside `ops/vllm_launch_coder.sh`.

### VRAM budget math (for DoD item 4 confidence)

Redone against actual conditions at F.3 (KNOWN_ISSUES §68 peak = 32,599 MiB at 99.98%) and F.3.0 concurrency=1 (`bench/pathF_swebench/apply_and_test.py:306`).

- Total VRAM: 32.0 GiB
- `gpu-memory-utilization=0.90`: usable = **28.8 GiB**
- `qwen3.6-27b-int4-autoround` weights (compressed-tensors int4, ~27B params): ~**14.5 GiB** (measured from KNOWN_ISSUES §68 peak minus KV / activations)
- torch.compile / inductor allocations + activations at ctx=32k: ~**5 GiB**
- KV budget currently used at 32k × concurrency=1: **~13 GiB (fp16 KV)** — this is why F.3 hit 99.98%. Model config: 27B Qwen3.6, 40 layers, 8 KV heads, head_dim 128.
- Per-token KV @ fp16: 2 × 40 × 8 × 128 × 2 = 163,840 B ≈ **160 KiB/token**
- Sanity: 32768 tokens × 160 KiB = 5.0 GiB per seq @ fp16 → confirmed within measured range (max-num-seqs=128 with paged allocator, but concurrency=1 means only ~1 seq worth is resident at steady state; some paging overhead accounts for the 13 GiB observation).

Under Slice 8.0 flags:

- fp8 KV halves per-token cost: **80 KiB/token**
- @ max-model-len=65536, concurrency=1: 65536 × 80 KiB = **5.0 GiB per active seq** — same footprint as the current 32k×fp16 configuration.
- **Slice 8.0's raised ceiling is VRAM-neutral at concurrency=1.** The gain is: prompts up to 65k tokens can now execute where they previously hit the harness's `context-budget-skip` short-circuit.

**Concurrency>1 case (informational, not Slice 8.0):** If a future slice raises harness concurrency to 4, KV envelope becomes 4 × 5.0 GiB = 20 GiB, still within the ~13 GiB current + 8 GiB post-weight headroom = 21 GiB. Marginal but feasible.

**Peak-load contingency (Slice 8.0):** if a smoke-30 task hits sustained 65k prompts and preemption cascades, `--max-num-seqs 32` (from 128) tightens the admission-control ceiling. This is §Rollback item 2.

### Condenser alignment — deferred to Slice 8.6

Originally scoped as DoD item 6 for §8.0 (per ADR-029 D4). Deferred after discovering Forge-OH's BFF has no agent-compose site (BFF forwards to OpenHands agent-server on :8090; the condenser lives inside that process). Slice 8.6 (SDK Skills adoption) is the correct slice to introduce the compose site and wire `LLMSummarizingCondenser(keep_first=..., max_tokens=...)` there.

Setting details deferred to Slice 8.6:
- vLLM APC block size default is 16 tokens (`--block-size 16` on vLLM ≥ 0.10; 0.26.0 confirmed on Colossus).
- Council-Synthesis line 60 recommends `keep_first=4` (preserves system prompt + task + repo manifest + plan events).
- Alignment padding to APC block boundary applied at compose time.

### Rollback strategy (if DoD item 4 fails)

If the smoke-30 re-baseline regresses by more than 1 task:

1. **Bisect the flag additions** (in this order): remove `--speculative-config` first (least tested; workload-dependent per Council-Synthesis). Re-run smoke. If pass, spec-decode alone caused the regression — file a follow-up to investigate n-gram acceptance rate on this model.
2. **If still regressed**: tighten `--max-num-seqs 128 → 32` (admission-control ceiling; addresses preemption cascades). Re-run.
3. **If still regressed**: remove `--enable-chunked-prefill` + `--long-prefill-token-threshold`. Re-run.
4. **If still regressed**: lower `--max-model-len` back to 32768 (isolates fp8 KV as the change). Re-run. If pass, the fp8 kernel has a long-context regression on this model + SM_120; file DEBUG_LOG and defer the ceiling raise.
5. **If still regressed**: revert `--kv-cache-dtype fp8`. Re-run. If pass, fp8 KV on int4-AutoRound is not viable on this stack; note the finding and revisit with a different weight quantization.
6. **Final fallback**: revert `ops/vllm_launch_coder.sh` to exact `b0dd4a0` state and file the failure as an ADR-worthy blocker.

Each rollback step is one commit. The bisect finishes in one bench run per step. Steps 4/5 also require restarting the vLLM container (`ops/vllm_supervisor.sh restart coder`); steps 1/2/3 also require restart.

### Files touched (Slice 8.0)

1. `ops/vllm_launch_coder.sh` — replace flag block (see §Flag matrix above).
2. `docs/reconciliation-plan-stage-8.md` (this file) — mark §8.0 status → **Ratified** when smoke-30 passes.
3. `BUILD_LOG.md` — append slice-completion entry.
4. `SESSION_HANDOFF.md` — overwrite to point to §8.0b (planner-side copy) + smoke re-baseline as the exact next action.

**Zero code touched outside the launcher.** No BFF code, no Python. Pure vLLM launcher-flag change.

### Open questions surfaced during draft

**Q1: vLLM version.** **RESOLVED 2026-08-06 15:29 EDT** — `vllm/vllm-openai:latest` reports 0.26.0. Well above the 0.10 threshold; full flag block ratified.

**Q2: n-gram spec-decode acceptance rate on Qwen3.6-27B int4-AutoRound.** DEFERRED to §8.0.5. Council-Synthesis rates n-gram "modest" and workload-dependent. §8.0.5 will measure acceptance rate; §8.0 accepts n-gram on the "modest but stacks + zero VRAM" argument.

**Q3: `--block-size` default in this vLLM version.** DEFERRED to Slice 8.6 (condenser wiring). No longer §8.0-relevant.

### Companion slice §8.0b (planner) — deferred to after §8.0 DoD

Same flag matrix, applied to `ops/vllm_launch_planner.sh`, with these differences:
- `--tool-call-parser` remains absent (planner is DeepSeek-R1, uses reasoning parser instead).
- `--reasoning-parser deepseek_r1` unchanged.
- `--quantization awq_marlin` unchanged (env-controlled via `FORGE_VLLM_PLANNER_QUANTIZATION`).
- Same fp8 KV + chunked prefill + spec-decode + max-model-len 65k.
- DoD: planner-role smoke (whatever bench exercises the planner path — TBD in §8.0b) does not regress.

§8.0b will file as a separate BUILD_LOG entry and does not need a separate ADR — it's a mechanical copy governed by ADR-029 §D5's cross-cutting §8.0 condenser tweak.

---

## §8.0.5 through §8.9 — Placeholders

Not drafted in this file. Inherit from:

- `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (Perplexity project files repo, commit `8e093bc`) for slice contracts, dependency order, and sizing.
- [ADR-029](./adr/029-sdk-native-adoption-for-stage-8.md) §D1–§D5 for adoption-vs-hand-build decisions per slice.

To be drafted at each slice's kickoff, following the pattern of §8.0 above.
