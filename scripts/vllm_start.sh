#!/usr/bin/env bash
# vLLM launcher for Forge-OH (OFF-PLAN F.18 experiment)
# Serves qwen3-coder-30b GGUF from Ollama's blob cache on :8500
set -euo pipefail

export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN

BLOB="${VLLM_GGUF_PATH:-/home/rmholston/.ollama/models/blobs/sha256-1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a}"
PORT="${VLLM_PORT:-8500}"
SERVED_NAME="${VLLM_SERVED_MODEL_NAME:-qwen3-coder-30b}"
LOG="${VLLM_LOG:-$HOME/.forge-oh/vllm.log}"

mkdir -p "$(dirname "$LOG")"

fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 2

# Sanity: blob must exist
[ -f "$BLOB" ] || { echo "GGUF not found at $BLOB" >&2; exit 1; }

# Trim VRAM headroom: 32GB total, model ~18.5GB, want ~4GB for KV cache
# max-model-len kept modest (32K) to avoid KV blowup on the 5090
exec ~/venv/vllm-new/bin/vllm serve "$BLOB" \
  --served-model-name "$SERVED_NAME" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --gpu-memory-utilization 0.85 \
  --max-model-len 32768 \
  --max-num-seqs 8 \
  --dtype float16 \
  --enable-prefix-caching \
  --hf-config-path Qwen/Qwen3-Coder-30B-A3B-Instruct
