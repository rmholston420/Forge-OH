---
name: benchmarking-discipline
description: How to design and run benchmarks so results are trustworthy, reproducible, and comparable across sessions. Use whenever measuring performance, comparing options (models, quantizations, algorithms, libraries, hardware configs), producing tok/s or latency numbers, or when a decision hinges on "which is faster/better." Covers warm-up, isolation, sample size, deterministic sampling, artifact-on-disk discipline, and quality-first-speed-second verdicts.
license: MIT
triggers:
  - benchmark
  - bench
  - tok/s
  - tokens per second
  - latency
  - throughput
  - "A/B test"
  - compare models
  - evaluate model
  - performance test
  - profile
  - profiling
  - quality vs speed
  - gold standard
  - baseline
  - model matrix
---

# Benchmarking Discipline

Applies to any performance comparison — LLM inference, algorithm speed, database queries, HTTP latency, build times.

## The Core Rule

**A benchmark you can't reproduce is not a benchmark. A benchmark you can't compare across sessions is not a benchmark.**

That means:
- Prompts / inputs live on disk, not embedded in the run command
- Outputs are saved as structured files, one per cell
- Every run captures its own metadata (git SHA, timestamp, hardware, software versions, sampling params)
- Nothing is measured from a warm start unless "warm start" is what you're testing

## Isolation — One Variable at a Time

If you change two things between runs, you can't attribute the difference. Enforce single-variable-per-comparison:

| Comparison | Vary | Hold constant |
|---|---|---|
| Model A vs Model B | model weights | prompts, sampling, runtime, hardware |
| Quant Q4 vs Q8 | quantization | model family, prompts, runtime, hardware |
| Ollama vs vLLM | runtime | model, quant, prompts, sampling |
| Prompt v1 vs v2 | prompt text | model, sampling, runtime |

If you want to compare four models across four quantizations, that's a **matrix** (16 cells), not a single "which is best" benchmark. Log every cell.

## Warm-Up

The first inference on a cold runtime is slower than steady-state — model loading, CUDA kernel compilation, cache warm-up all happen once. Discard warm-up samples.

Standard pattern: 1–3 warm-up prompts, then N measured prompts. The warm-up prompts should be representative of the measured prompts (same length, same style) so kernels are compiled for the right shapes.

## Sample Size

- **N=1** — not a benchmark, that's a demo
- **N=3** — enough to notice a huge gap, useless for close calls
- **N=5** — usable minimum for early screening
- **N=10+** — required before publishing a "winner"
- **N=30+** — for statistical claims (mean ± stddev, confidence intervals)

Report median for latency (more robust to outliers than mean). For tok/s report both mean and median — divergence signals variance issues.

## Determinism — Sampling Params Matter

Random sampling makes results uncomparable. For any benchmark:

- **Coder-style tasks** (code generation, structured output): `temperature=0`, `top_p=1.0`. Deterministic.
- **Reasoning / planner tasks**: `temperature=0.6-0.7`, `top_p=0.9-0.95`, but PIN the random seed if the runtime supports it (`--seed 42`).
- **Never** compare two models with different sampling params. Fix the params, fix them across all cells.

If you're benchmarking creativity/diversity, use a fixed seed AND report N>=10 samples per prompt.

## Prompts on Disk

Prompts belong in files, not command lines. Reasons:

- Reproducible: `sha256sum prompts/*.md` gives you a checksum of the input set
- Diffable: prompt v2 vs v1 shows up in git
- Sharable: someone else can rerun your bench without pulling it from your shell history

Structure:

```
bench/
  prompts/
    coder/
      code-01-add-cli-flag.md
      code-02-refactor-loop.md
      ...
    planner/
      plan-01-design-schema.md
      ...
  results/
    2026-08-06T14-32Z/
      qwen3-coder-30b-awq/
        cell-code-01.json
        cell-code-02.json
        summary.json
      qwen3-coder-30b-nvfp4/
        ...
      manifest.json    # hardware + software versions
```

Every result JSON captures: prompt path + sha, response text (raw), sampling params, wall time, tok/s, tokens generated, output-tokens-per-sample.

## Reasoning-Block Stripping

For models with `<think>...</think>` (Qwen3.6+, R1 family, o1-style):

- Include the think tokens in tok/s (that's what the model actually generated)
- **Strip them before quality scoring** — the user only sees the post-think answer
- Never count think-tokens toward the "useful output length" for cost analysis

If you don't strip, a thinking model looks 3–5x more verbose than a non-thinking model, corrupting all quality-per-token comparisons.

## Quality First, Speed Second

The trap: "Model B is 40% faster." → but is Model B's output usable?

Verdict rule: **speed is a tiebreaker, not a metric.** If Model A produces a working PR and Model B produces a buggy PR that's 40% faster, Model A wins. No exceptions.

Scoring order:
1. **Quality gate** — does the output pass a hard filter (tests pass, JSON parses, code compiles)?
2. **Quality score** — rubric-based, ideally graded against a gold-standard reference
3. **Speed** — tok/s or latency, only among cells that passed 1 and 2

Cells failing (1) get 0. Cells passing (1) get scored by (2). Speed is a tiebreaker among cells with equal (2) scores.

## Gold Standard References

For each prompt, have a reference "gold" answer written by the best available source (a stronger model like Perplexity's frontier tier, or a human expert). Score outputs against the gold, not against each other.

Reasons:
- Two mediocre models can agree with each other and diverge from correct
- Gold-standard scoring is comparable across sessions; head-to-head is not
- New models added later can be scored against the same gold without re-running the whole matrix

## Metadata Manifest

Every benchmark run writes a `manifest.json` at the top of the results dir:

```json
{
  "timestamp": "2026-08-06T14:32:00Z",
  "git_sha": "abc123...",
  "hardware": {
    "gpu": "RTX 5090",
    "vram_gb": 32,
    "driver": "610.43.02",
    "ram_gb": 128,
    "cpu": "..."
  },
  "software": {
    "python": "3.12.4",
    "torch": "2.5.1+cu129",
    "vllm": "0.10.2",
    "ollama": "0.3.14"
  },
  "sampling": {"coder": {...}, "planner": {...}},
  "prompt_set_sha": "<sha256 of concatenated prompts>",
  "warm_up_prompts": 2,
  "measured_prompts_per_cell": 10
}
```

Without this manifest, the numbers are unreproducible six months from now.

## Reporting

- Report medians and IQRs, not just means (means hide outliers)
- Report absolute numbers AND relative deltas ("Model B is 1.4x faster" is more useful than "Model B is 87 tok/s")
- Report the losing configurations too — "we tried FP8 and it OOMed" is data, not noise
- Report the sample size prominently — a bench of N=3 is not a bench of N=30

## Anti-Patterns

- ❌ Timing code with `time` around a script that includes startup (measures process launch, not the thing you care about)
- ❌ Warm-start comparisons dressed up as "we ran it three times and took the fastest" (measures cache, not the algorithm)
- ❌ Comparing models with different sampling params
- ❌ Ranking by tok/s without a quality filter
- ❌ Single-prompt benchmarks passed off as model evaluations
- ❌ Not saving the raw outputs (can't re-score later)
- ❌ Running benchmarks with other GPU workloads active
- ❌ Publishing a "winner" without CI bounds or a rerun
- ❌ Cherry-picking prompts to favor a preferred model
- ❌ Changing the prompt set mid-matrix

## Minimum Viable Benchmark Checklist

Before running:

1. Prompts committed to disk with a stable path
2. Sampling params fixed and documented
3. Warm-up count and measured count chosen
4. Output directory named with timestamp + descriptor
5. Manifest fields identified

After running:

1. Every cell has a raw output file
2. Manifest is written
3. Reasoning blocks stripped before quality scoring
4. Quality gate applied before speed comparison
5. Report includes N, medians, IQR, sampling params, hardware
6. Failed cells (OOM, errors) recorded, not dropped
