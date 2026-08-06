---
name: deep-research
description: How to conduct multi-source investigations that produce trustworthy synthesis — not just a link dump. Use whenever the task requires researching an unfamiliar topic across multiple sources, comparing options, tracing evolution of a technology, evaluating claims, or building a knowledge artifact for future reference. Enforces source diversity, provenance tracking, contradiction reconciliation, and structured artifact output.
license: MIT
triggers:
  - research
  - investigate
  - deep dive
  - compare options
  - evaluate
  - literature
  - primary source
  - state of the art
  - "state-of-the-art"
  - survey
  - synthesis
  - white paper
  - citations
---

# Deep Research

Applies to investigations that require reading multiple sources and producing synthesis — not one-shot fact lookups.

## When to Use

- Comparing 3+ options across multiple dimensions
- Understanding an unfamiliar technology / library / concept end-to-end
- Building a knowledge artifact (wiki page, ADR context section, blog post source)
- Evaluating a claim that needs corroboration
- Tracing evolution of a topic (this changed when, why, what came before)

**Do NOT use** for:
- Single-fact lookups (a search does that)
- Debugging your own code (that's `debug-first-response`)
- Reading one document to answer one question

## The Core Discipline

**Every claim in your final artifact traces to a URL. Every URL you cite you have actually read.**

That means:
- Log every source as you read it (URL + one-line takeaway)
- If two sources disagree, note it and resolve or flag the disagreement
- Never restate a claim without knowing which source made it
- Never cite a source you only skimmed the title of

## Research Loop

### Step 1 — Frame the Question

Write down what you're trying to answer, in one sentence. If you can't, the question is too vague — refine it first.

Good: "What are the tradeoffs between AWQ and NVFP4 quantization for Qwen3-30B on RTX 5090?"
Bad: "Research quantization."

### Step 2 — Source Discovery

Start broad. Search 3–5 sources of DIFFERENT TYPES:

| Source type | Example |
|---|---|
| Primary / official | Official docs, GitHub README, spec, paper |
| Vendor blog | Announcement post, engineering blog |
| Independent expert | Blog, newsletter, conference talk |
| Community discussion | GitHub issues, Discord/Reddit threads, HN discussion |
| Benchmark / study | Independent evaluation, MLPerf, standardized comparison |

**Never** rely on one source type. Marketing blogs skip failure modes; GitHub issues skip successes; benchmarks miss caveats.

### Step 3 — Read, Don't Skim

For each source that looks relevant:

1. Read the full text (or the relevant section end-to-end)
2. Log the source: URL, date published, author, one-line takeaway
3. Extract concrete claims (numbers, dates, decisions, tradeoffs)
4. Note any claim that surprises you — those are the ones to verify

Keep sources in a structured log:

```markdown
## Sources

### [1] Qwen3-30B quantization guide — 2026-04-12
URL: https://github.com/QwenLM/Qwen3/blob/main/docs/quantization.md
Author: QwenLM team
Takeaway: Recommends AWQ over GPTQ for Qwen3 due to better perplexity on long-context prompts.
Key claims:
- AWQ-4 loses ~2% quality vs BF16 on MMLU
- NVFP4 is 1.4x faster on Blackwell than AWQ-4
```

### Step 4 — Reconcile Contradictions

If sources disagree, do NOT pick one arbitrarily. Options:

1. **Both are right in different contexts** → note the context boundary
2. **One is stale** → check dates; newer info wins if the field changed
3. **One is misinformed** → read the primary source both are citing
4. **Both are speculating** → flag as open question, not resolved

Example:

> Sources [3] and [7] disagree on FP8 quality on Qwen3-30B. Source [3] (April 2026 vLLM blog) reports 0.5% MMLU loss; source [7] (June 2026 independent benchmark) reports 3.2% loss on the same benchmark. Difference: [3] used the E4M3 variant with per-tensor scaling; [7] used the E5M2 variant. Resolution: FP8 quality depends heavily on scaling method and calibration set. Both numbers are true for their configurations.

### Step 5 — Synthesize

Write the synthesis from the CLAIMS log, not from memory:

- Group related claims into themes
- Order by importance / decision-relevance, not by chronology of your reading
- Cite every claim: `AWQ loses ~2% on MMLU [1]`
- Include failed / rejected options with reasoning ("we did not choose X because Y [4]")
- Flag open questions and contradictions explicitly

### Step 6 — Artifact Output

Structure the artifact for future re-reading (yours or another agent's):

```markdown
# <Topic>

**Question**: <the framing question>
**Date**: <today>
**Status**: <Draft | Reviewed | Outdated>

## Summary
<3–5 sentences. The most useful takeaways.>

## Findings
<H2/H3 sections. Each claim cites [n].>

## Tradeoffs
<Table or bullets comparing options.>

## Open Questions
<What's unresolved. What would you research next.>

## Sources
<Full source list with URLs, dates, one-line takeaways.>
```

## Source Quality Ranking

Not all sources are equal. Rough ranking:

1. **Primary source** — the actual specification, code, or announcement
2. **Peer-reviewed / independently reproduced** — papers with citations, benchmarks with public methodology
3. **Vendor documentation** — accurate for capabilities, biased for tradeoffs
4. **Expert practitioner blogs** — accurate for real-world use, sample size of one
5. **Community discussion** — surfaces failure modes vendors hide, but often outdated or wrong
6. **AI-generated summaries** — treat as a search hint, never as a source

## Anti-Patterns

- ❌ Reading only one source
- ❌ Reading only recent sources (misses context, history, why-decisions-were-made)
- ❌ Skimming the intro and citing the whole paper
- ❌ Copying paragraphs from sources into your synthesis without integration
- ❌ Stating claims without a citation
- ❌ Not tracking source publication dates (a 2023 claim about "current" may be 3 versions stale)
- ❌ Dismissing a contradiction rather than reconciling it
- ❌ Reading past the point of diminishing returns (10 sources on the same theme is 8 too many)
- ❌ Producing a link dump instead of synthesis
- ❌ Missing counterexamples that would nuance the conclusion
- ❌ Trusting a marketing benchmark without checking methodology
- ❌ Confusing "many sources agree" with "the claim is true" (they may all cite the same wrong source)

## Time Budget

Deep research is expensive. Set a budget before starting:

| Investigation scope | Sources | Time |
|---|---|---|
| One-page briefing | 3–5 | 30 min |
| Decision-quality comparison | 5–10 | 2 hours |
| Wiki / knowledge artifact | 10–20 | 4–8 hours |
| Full literature review | 30+ | days |

If you're 50% over budget and still finding new sources, either narrow the question or accept the artifact will be shallower than planned.

## Checklist Before Publishing

1. Framing question is stated and answered
2. Summary is 3–5 sentences and independently readable
3. Every claim in findings has a citation
4. Sources are diverse (at least 3 types from the table above)
5. Contradictions are noted, not glossed
6. Failed / rejected options are documented
7. Open questions are explicit
8. Source list has URL + date + one-line takeaway for each entry
9. Length matches scope (a 3-source briefing isn't 30 pages)
10. Artifact can be re-read in 6 months and still be understood
