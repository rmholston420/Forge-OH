# ADR 001: Use Ollama-First, vLLM Fallback Routing

**Status:** Accepted  
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
