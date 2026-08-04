# ADR 001: Use Ollama-First, vLLM Fallback Routing

> **STATUS AMENDMENT (2026-08-04):** This ADR is **AMENDED · superseded
> by ADR-009 for the F.19+ two-role router**. From F.19-pre onward, the
> Coder/Planner router in `bff/services/model_router.py` uses **vLLM as
> the primary backend** (`qwen3.6-35b-nvfp4` for Coder, `qwen3-thinking-2507-awq`
> for Planner) with Ollama as the fallback. See
> [`docs/adr/009-local-llm-selection.md`](../../docs/adr/009-local-llm-selection.md)
> for the bench evidence (F.19-pre 8-cell matrix) and the exact model /
> quantization / port assignments. The GPU-tenancy discipline that makes
> this swap safe is codified in `ops/vllm_supervisor.sh` and verified by
> `ops/test_supervisor.sh` (21/21 offline tests).
>
> This ADR is preserved unedited below for historical context (F.15 era).
> Do NOT rely on the routing policy stated in the "Decision" section for
> F.19+ work — use ADR-009.

**Status:** Amended · superseded by ADR-009 for F.19+ router  
**Date:** 2026-07

## Context

Forge-OH targets local/on-premise deployments where a cloud LLM API is either
unavailable or undesirable. We need a model routing strategy that is reliable,
privacy-preserving, and degrades gracefully.

## Decision

All inference requests are routed through `bff/services/model_router.py`:

1. **Primary:** Ollama (`devstral-small:24b` for agentic tasks, `qwen3:14b` for
   fast/overflow tasks). Ollama is checked first via a health call to `/api/tags`.
2. **Fallback:** vLLM (configured via `VLLM_FALLBACK_MODEL` env var). Used only
   when Ollama is unavailable or the context length exceeds `DEVSTRAL_CTX_LIMIT`
   (28,000 tokens).
3. **No cloud fallback.** If both are unavailable, a `ModelUnavailableError` is
   raised and the user is shown a clear error message.

## Consequences

- The frontend has zero model awareness. Model names never appear in the browser.
- The 28K token KV cache limit for Devstral must be monitored. Context overflow
  routes to the fast model automatically.
- Never go below Q4_K_M quantization.
