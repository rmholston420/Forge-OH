# ADR-001: Use Ollama as Primary LLM Backend

**Status**: Accepted  
**Date**: 2026-07-12

## Decision

Ollama is the primary local LLM backend. vLLM is the fallback.

## Rationale

- Air-gapped / local-first operation preserves data privacy
- RTX 5070 (16 GB VRAM) fits Devstral Small 24B at Q4_K_M (~16 GB)
- Ollama v0.31.2 has the latest Devstral and Qwen3 support
- KV cache routing: context > 28K tokens routes to Qwen3 14B (~9 GB weights)

## Model Routing

| Task | Model | Reason |
|------|-------|--------|
| Agentic / multi-file | devstral-small:24b | Best agentic code quality |
| Fast scripting / long context | qwen3:14b | 9 GB leaves 7 GB for KV cache |
| IDE autocomplete | codestral:22b | FIM-optimized |
