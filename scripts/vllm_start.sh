#!/usr/bin/env bash
# vLLM launcher for Forge-OH (OFF-PLAN F.18 experiment).
#
# Serves qwen3-coder-30b GGUF from Ollama's blob cache on :8500. Calls
# ``vllm_stop.sh`` first so no ghost EngineCore worker keeps VRAM pinned.
#
# Required Colossus overrides for RTX 5090 (SM_120) and GGUF weights:
#   VLLM_USE_FLASHINFER_SAMPLER=0   FlashInfer's SM whitelist rejects SM_120.
#   VLLM_ATTENTION_BACKEND=FLASH_ATTN
#   --dtype float16                 GGUF loader rejects bf16.
#   --hf-config-path Qwen/...       GGUF ships no tokenizer config.
#
# Usage:
#   ./scripts/vllm_start.sh            # foreground (exec)
#   nohup ./scripts/vllm_start.sh > ~/.forge-oh/vllm.log 2>&1 &  # background
set -euo pipefail

export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN

BLOB="${VLLM_GGUF_PATH:-/home/rmholston/.ollama/models/blobs/sha256-1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a}"
PORT="${VLLM_PORT:-8500}"
SERVED_NAME="${VLLM_SERVED_MODEL_NAME:-qwen3-coder-30b}"
LOG="${VLLM_LOG:-$HOME/.forge-oh/vllm.log}"
VENV_BIN="${VLLM_VENV_BIN:-$HOME/venv/vllm-new/bin/vllm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$(dirname "$LOG")"

# Clean any previous instance so no ghost worker holds VRAM.
if [ -x "$SCRIPT_DIR/vllm_stop.sh" ]; then
    "$SCRIPT_DIR/vllm_stop.sh" "$PORT" || true
else
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    pkill -9 -f 'VLLM::EngineCore' 2>/dev/null || true
    pkill -9 -f 'vllm serve' 2>/dev/null || true
    sleep 2
fi

# Sanity: blob and venv must exist.
[ -f "$BLOB" ] || { echo "GGUF not found at $BLOB" >&2; exit 1; }
[ -x "$VENV_BIN" ] || { echo "vLLM binary not found at $VENV_BIN" >&2; exit 1; }

# 32GB total VRAM, model ~18.5GB, ~4GB KV budget. max-model-len is modest
# (32K) to avoid KV blowup on the 5090.
exec "$VENV_BIN" serve "$BLOB" \
  --served-model-name "$SERVED_NAME" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --gpu-memory-utilization 0.85 \
  --max-model-len 32768 \
  --max-num-seqs 8 \
  --dtype float16 \
  --enable-prefix-caching \
  --hf-config-path Qwen/Qwen3-Coder-30B-A3B-Instruct
