# ADR-013 — Qwen3.6-27B as canonical coder + planner

**Status:** Proposed (bench pending — see `bench/pathE_qwen36_27b/`)
**Supersedes:** ADR-009 §1, §2 (model-selection layer only; routing contract remains ADR-012)
**Superseded by:** —

## Context

ADR-009 selected `qwen3.6-35b-a3b-nvfp4` (coder) and `qwen3-thinking-2507-awq` (planner) as canonical role models. Since then, two developments make Qwen3.6-27B (dense, Apache 2.0, released 2026-07) a strong candidate to displace both:

1. **Hybrid Gated-DeltaNet/Attention architecture** — only 16 of 64 layers use standard KV cache; the rest use fixed-size linear-attention state. KV memory barely grows from 32K → 128K context. Reported field VRAM at 32K context: ~22 GB (INT4) or ~26 GB (NVFP4) — vs the 35B-A3B baseline at 31.8 GB (thin margin).
2. **Quality** — Qwen3.6-27B reports 98% of Qwen3.6-35B-A3B BF16 quality at NVFP4 (GPQA 0.198 vs 0.207). Coder-role AutoRound INT4 (Lorbus/Qwen3.6-27B-int4-AutoRound) reports 100-160 tok/s on RTX 5090.

Deep-research reports (2026-08-04):
- `/home/user/workspace/coder_llm_research.md`
- `/home/user/workspace/planner_llm_research.md`

Both roles converge on the same base model (Qwen3.6-27B) but different quants:
- **Coder:** Lorbus AutoRound INT4 (wider VRAM margin, higher tok/s)
- **Planner:** nvidia NVFP4 (higher-precision, quality-first)

## Decision

**PENDING BENCH.** This ADR is authored as a stub. It will be ratified only if the Path E bench in `bench/pathE_qwen36_27b/` demonstrates:

- **c01 (Qwen3.6-27B-int4-AutoRound coder) quality ≥ c02 (qwen3.6-35b-a3b-nvfp4 baseline)** within the 3-point tie window
- **c04 (Qwen3.6-27B-NVFP4 planner) quality > c05 (qwen3-thinking-2507-awq baseline)** — planner is quality-first, no speed tiebreak
- **Zero c01/c04 errors** across 3-run × 3-prompt matrix
- **c01 VRAM peak < 28 GB** at 32K context
- **c04 VRAM peak < 28 GB** at 32K context

If all criteria met, the canonical role models flip to:

- `LLM_CODER_MODEL="qwen3.6-27b-int4-autoround"`
- `LLM_PLANNER_MODEL="qwen3.6-27b-nvfp4"`

And `MODEL_ROUTER_CATALOG` (from ADR-012) becomes:

```python
MODEL_ROUTER_CATALOG = {
    "coder":   RoleCatalog(
        canonical="qwen3.6-27b-int4-autoround",
        compatible={"qwen3.6-27b-int4-autoround", "qwen3.6-27b-nvfp4", "qwen3-coder:32k"},
    ),
    "planner": RoleCatalog(
        canonical="qwen3.6-27b-nvfp4",
        compatible={"qwen3.6-27b-nvfp4", "qwen3-thinking-2507-awq"},
    ),
}
```

Rationale for the role-separated `compatible` sets:
- Coder-role `compatible` includes the NVFP4 variant so a preset can override for a longer-context planning task; excludes the pure-thinking Qwen3-Thinking model because it lacks the `qwen3_coder` tool-call parser.
- Planner-role `compatible` excludes the AutoRound INT4 variant because it ships without the reasoning parser; the operator can still route to `qwen3-thinking-2507-awq` as a rollback.

## Alternatives considered

1. **Keep ADR-009 baseline unchanged.** Rejected pending bench: field evidence shows Qwen3.6-27B has 12 GB more KV headroom at 32K context and reports higher quality per byte.
2. **Move planner to QwQ-32B** (Apache 2.0, `deepseek_r1` parser). Held as runner-up. Longest track record but larger footprint and older architecture. Escalation path if c04 fails but c05 also drops.
3. **Use `Qwen/Qwen3.6-27B-FP8` (official).** Rejected: 27.9 GB weights alone leave zero KV budget on a 32 GB card; also confirmed broken on RTX 5090 (vLLM GitHub #41695).
4. **DeepSeek R2 / other content-farm suggestions.** Rejected: does not exist. Confirmed hallucinated in multiple third-party sources.

## Consequences

If ratified:

- **Files changed:**
  - `bff/services/model_router.py` — `MODEL_ROUTER_CATALOG` seed data
  - `bff/config.py` (or equivalent env source) — `LLM_CODER_MODEL`, `LLM_PLANNER_MODEL` defaults
  - `docs/adr/README.md` — new row for ADR-013
  - `PORTING_LEDGER.md` — new HuggingFace weights vendored
- **Procedures affected:** vLLM launcher wrappers for coder (`:8501`) and planner (`:8511`) must pull the new model dirs before restart.
- **Tests to update:** `test_model_router.py` (any that hardcode the canonical name) — should already be catalog-driven per ADR-012.
- **ADR-012 amended:** the catalog-seed example section replaced with the new seed.
- **ADR-009 amended:** status line updated to `Superseded (model-selection layer) by ADR-013`. Original text preserved.

If rejected:

- ADR-013 remains `Proposed → Rejected` with bench results attached; ADR-009 stays canonical.

## Bench execution

See `bench/pathE_qwen36_27b/README.md` for the run book. Bench artifacts land under `~/.forge-oh/bench_pathE/` (gitignored). Only this ADR is committed with the verdict.

## References

- ADR-009 (local LLM selection — coder + planner)
- ADR-012 (dual-mode model routing)
- `bench/pathE_qwen36_27b/README.md`
- `/home/user/workspace/coder_llm_research.md`
- `/home/user/workspace/planner_llm_research.md`
- vLLM GitHub #40807 (CUDA-graph crash — Qwen3.6 workaround: `--enforce-eager` if hit)
- vLLM GitHub #40831 (TurboQuant × spec-decode quality regression)
- vLLM GitHub #41695 (Qwen3.6-FP8 broken on RTX 5090 — rejected quant)
