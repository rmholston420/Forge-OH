# ADR 001: Use Ollama as Primary Model Backend

**Status**: Accepted  
**Date**: 2026-07-01

## Context

Forge-OH runs on a workstation with an NVIDIA RTX 5070 (16 GB VRAM). The operator is privacy-conscious and prefers air-gapped, local inference where possible. Cloud APIs introduce latency, cost, and data exposure risk.

## Decision

All model inference routes through Ollama (local) first. vLLM (local, port 8000) is the fallback when Ollama is unavailable or when context exceeds the KV cache budget. Cloud APIs are not used unless explicitly opted in per-request.

## Model Assignments

| Task | Model | Backend |
|------|-------|---------|
| Agentic workflows, multi-file refactoring | Devstral Small 24B (Q4_K_M) | Ollama |
| Fast scripting, quick summaries | Qwen3 14B (Q4_K_M) | Ollama |
| IDE autocomplete (FIM) | Codestral 22B (Q4_K_M) | Ollama |
| Overflow / vLLM fallback | configurable | vLLM |

## KV Cache Budget

- Set `PARAMETER num_ctx 32768` in all Ollama Modelfiles.
- Devstral 24B at Q4_K_M uses ~16 GB — KV cache headroom near zero at long context.
- For sessions expected to exceed 16K tokens, route to Qwen3 14B (9 GB weights, ~7 GB free for KV).
- `DEVSTRAL_CTX_LIMIT = 28_000` is the soft limit in `model_router.py`.

## Quantization Floor

**Never go below Q4_K_M.** Q3_K_S introduces syntax errors in generated code.

## Consequences

- All model routing logic lives in `bff/services/model_router.py`.
- The frontend never selects models — routing is a BFF responsibility.
- Env vars: `DEVSTRAL_MODEL`, `FAST_MODEL`, `VLLM_BASE_URL`, `VLLM_FALLBACK_MODEL`.
