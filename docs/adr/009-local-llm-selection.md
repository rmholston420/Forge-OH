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

### 3a. Topology: dual-port + swap-on-demand supervisor

A single RTX 5090 (~30 GiB usable) cannot hold both
`qwen3.5-nvfp4` (coder) and `qwen3-thinking-2507-awq` (planner)
resident simultaneously. Two options were considered:

- **Single vLLM, one role at a time** — simpler process model, but
  every role switch pays a full weight-reload cost (~30-60s) and the
  BFF must serialize coder/planner traffic.
- **Dual-port with swap-on-demand supervisor** — one vLLM launcher
  per role, each on its own port (`:8501` coder, `:8511` planner);
  only one is running at a time; a small supervisor script under
  `ops/vllm_supervisor.sh` stops the idle role and starts the
  requested role on the first BFF request that misses.

**Decision: dual-port + supervisor.** Rationale:

- BFF-side routing stays cache-friendly — coder and planner have
  stable URLs; the supervisor handles the VRAM contention below the
  routing layer.
- Warm-hits stay fast (no per-request reload); only role transitions
  pay the swap cost, and planner calls are infrequent enough that
  most workloads sit in one role for extended stretches.
- Failure isolation is cleaner: a crashed planner does not take down
  the coder port config.

The supervisor is F.19 scope; ADR-009 fixes only the topology choice.

### 3b. Token budgets: coder 2048, planner 8192

F.19-pre ran coder cells at `max_completion_tokens=2048` and planner
cells at `4096`. Every thinking cell hit the 4096 ceiling on Prompt 3;
c08 truncated mid-list, c05/c06/c07 returned empty final content after
burning the budget in hidden reasoning.

**Decision:** Coder budget stays at **2048** (no ceiling hits on any
coder cell). Planner budget raised to **8192** as the default for the
rewired router in F.19. Rationale:

- 8192 is the smallest bump that gives the qwen3-thinking family room
  to finish a 6-10 commit atomic plan after its reasoning trace.
- Latency cost is bounded: only the tokens the model actually emits
  are billed, and c08 was already the slowest cell — an 8192 ceiling
  does not force it slower on shorter answers.
- If the follow-up re-bench (§Follow-ups 1) shows c05 or c06 finishes
  P3 cleanly at 8192 and is materially faster than c08, the planner
  pick is revisited under a superseding ADR. Until then c08 is the
  planner.

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
- **Quantization flag is not uniform across the two role models.**
  - c04 coder (`qwen3.5-nvfp4`) **requires** `--quantization modelopt_fp4`;
    vLLM 0.26 does not autodetect ModelOpt-FP4 for this checkpoint
    (bench cell c04 confirmed).
  - c08 planner (`qwen3-thinking-2507-awq`) ships as **compressed-tensors**
    and must be launched with **no** `--quantization` flag; vLLM
    autodetects from `config.json.quantization_config.format` (bench
    cell c08 confirmed). Passing `--quantization awq` breaks it.
  - Rule: check `config.json.quantization_config.format` and set the
    flag only when the format is NOT `compressed-tensors`.
- **F.19 supervisor uses the Docker image permanently, not the native
  venv.** The Colossus native venv (`~/venv/vllm-new`, vLLM 0.10.2)
  predates `qwen3_5_moe` support and cannot run either role model.
  Migration was tracked as Follow-up 4 (F.19.5) but closed as
  deferred indefinitely after F.19.4 measurements showed Docker
  cold-start is CUDAgraph-compile-bound, not container-bound; see
  Follow-ups §4.
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

## Follow-ups

1. **F.19-pre-b re-bench** (before F.19 wiring lands): re-run c05,
   c06, c07 on Prompt 3 only with `max_completion_tokens=8192`. If
   any finishes cleanly and outscores c08 on P3 (23), the planner
   pick shifts to that cell under a superseding ADR. c08 remains the
   planner default in the interim; F.19 wiring proceeds against c08
   regardless of the re-bench outcome so the two efforts can run in
   parallel.
2. Ollama upstream tracking: watch for a fix to
   `chat_template_kwargs.enable_thinking` for qwen3.5-MoE. If
   corrected, revisit c03 as a fast-Coder candidate.
3. Reconcile BFF port assignment (Forge-OH BFF is on :8081; the
   `colossus-ops` skill lists :8000). Decision: BFF stays on **8081**
   (already wired end-to-end, F.18c verified). Update
   `colossus-ops` skill in a separate pass.
4. **F.19.5 native-venv unification — CLOSED as deferred
   indefinitely (2026-08-03, post-F.19.4).**

   Original hypothesis: native `vllm serve` would be ~2x faster than
   Docker cold-start and would avoid `--ipc=host` VRAM allocator
   quirks.

   Measurement (F.19.4 Phase 2 on Colossus with vLLM 0.26.0 in
   Docker, RTX 5090 SM_120):
     - Coder cold swap:  245-292s
     - Planner cold swap: 141-156s
     - Warm reuse: <2s

   Container startup contributes <5s of the cold-swap time; the
   dominant cost (>95%) is CUDAgraph compile for the AWQ/NVFP4
   quantizations on Blackwell. Native venv would produce the same
   CUDAgraph work and the same 240s cold-swap. The promised ~2x
   speedup is not real — it would be ~2%.

   Costs of pursuing F.19.5:
     - vLLM 0.10 → 0.26 upgrade risks breaking the F.18 :8500
       legacy `qwen3-coder-30b` GGUF instance (breaking API
       changes documented across that range).
     - Launcher scripts revert from vetted `vllm/vllm-openai:latest`
       image to a bespoke venv install; extra maintenance surface.
     - Zero observed downside to Docker in F.19.1b through F.19.4:
       no --ipc=host issues, no VRAM allocator quirks, clean stop
       via `docker rm -f`.

   Decision: keep Docker permanently. F.18 :8500 GGUF instance
   stays on native venv 0.10.2 (its known-good state). The two
   codepaths coexist without interference (different ports,
   different processes, different vLLM versions).

   Revisit only if a concrete Docker limitation is observed.

5. **Supervisor GPU-tenancy discipline — landed 2026-08-04 (post-G.1).**

   Symptom that motivated this: after G.1 merged to main, the coder
   vLLM container `forge-vllm-coder` `Exited(1)` immediately with
   `ValueError: Free memory on device cuda:0 (24.85/31.39 GiB) on
   startup is less than desired GPU memory utilization (0.9, 28.25
   GiB)`. Root cause was pure GPU contention — Ollama was still
   holding ~6.5 GB VRAM at the moment `ops/vllm_launch_coder.sh`
   ran `docker run`. The launcher scripts and `ops/vllm_supervisor.sh`
   did NOT stop Ollama or verify `memory.free` before invoking
   `docker run`; the discipline lived only in the `forge-oh-llm-serving`
   skill notes.

   Decision: encode the discipline in `ops/vllm_supervisor.sh`
   itself. The supervisor is the swap orchestrator per §3a; managing
   GPU tenancy across all launcher paths (direct CLI, BFF cache-miss
   `ensure`, systemd) is its job.

   Implementation (`slice/vllm-supervisor-gpu-discipline`, PR into
   main):
     - New helper `_stop_ollama()` — idempotent, no-ops if Ollama
       unit is not installed. Combines `sudo systemctl stop ollama`
       (when the unit is present) with `pkill -x ollama` and
       `pkill -f 'ollama runner'` as belt-and-braces.
     - New helper `_free_gpu_for_vllm()` — calls `_stop_ollama`,
       then polls `nvidia-smi --query-gpu=memory.free` every 2s
       until `>= VLLM_MIN_FREE_MIB` (default 28000 MiB ≈ 0.9 × 31.4 GiB
       card) or `VLLM_GPU_FREE_TIMEOUT` (default 30s) elapses.
       Returns non-zero on timeout so `cmd_up` short-circuits
       before `docker run` can crash.
     - `cmd_up coder` and `cmd_up planner` now call
       `_free_gpu_for_vllm` between `_stop_role` and `_launch`.
     - New CLI subcommand `check` — dry-runs the discipline
       (reports free vs required VRAM, exits 0/1) without
       stopping Ollama or launching anything. Useful for the
       DEBUG_LOG cold-boot sequence and for CI-free verification.
     - New env knobs: `VLLM_MIN_FREE_MIB`, `VLLM_GPU_FREE_TIMEOUT`,
       `VLLM_SKIP_OLLAMA_STOP` (for machines without Ollama
       installed or when the caller has already stopped it).
     - Offline test suite `ops/test_supervisor.sh`
       (14 cases, all pass) exercises the helpers with PATH-injected
       stubs for `nvidia-smi`, `systemctl`, `sudo`, `pkill`, `docker`,
       `fuser`, `ss`, `curl`. Supervisor gained a library-mode
       guard (`(return 0 2>/dev/null) && return 0` before dispatch)
       so tests can source it without triggering the CLI usage
       branch.

   Consequences:
     - `cmd_up` is idempotent w.r.t. Ollama state: caller does not
       need to pre-stop Ollama; the supervisor handles it.
     - `_free_gpu_for_vllm` requires `sudo -n` (passwordless) to stop
       Ollama via systemd. On Colossus this is already configured. On
       a machine without passwordless sudo, `pkill` still runs and
       usually suffices for a user-run `ollama serve` process.
     - No changes to `ops/vllm_launch_coder.sh` or
       `ops/vllm_launch_planner.sh`. The launchers stay focused on
       `docker run` construction; policy lives in the supervisor.
     - Reversibility: setting `VLLM_SKIP_OLLAMA_STOP=1` restores the
       pre-slice behavior for callers that need it.

---

_Bench methodology, per-prompt scoring, and length-ceiling forensics
in `bench/f19pre/results/scores_20260803.md`._
