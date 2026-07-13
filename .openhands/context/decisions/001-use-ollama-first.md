# ADR 001 — Use Ollama as Primary LLM Backend

**Status**: Accepted  
**Date**: July 2026

## Context

Forge-OH operates in potentially air-gapped environments on local hardware (RTX 5070, 16 GB VRAM). Cloud LLM APIs introduce latency, cost, and privacy concerns for code that may be proprietary.

## Decision

All model routing uses Ollama as the primary backend, with vLLM as a local fallback. Cloud models are optional and disabled by default.

**Model tiers:**
- **Primary (agentic):** Devstral Small 24B @ Q4_K_M via Ollama (~16 GB VRAM)
- **Fast (scripting):** Qwen3 14B @ Q4_K_M via Ollama (~9 GB VRAM)
- **Fallback:** vLLM at `localhost:8001` with configurable model via `VLLM_FALLBACK_MODEL`
- **IDE autocomplete:** Codestral 22B @ Q4_K_M via Ollama

## Consequences

- Model routing is entirely BFF-side — the frontend never selects models
- `DEVSTRAL_CTX_LIMIT = 28_000` is enforced; sessions exceeding this route to Qwen3
- Never go below Q4_K_M quantization — Q3_K_S introduces syntax errors in generated code
- The `VLLM_FALLBACK_MODEL` env var must be set to match whatever model is loaded in vLLM
