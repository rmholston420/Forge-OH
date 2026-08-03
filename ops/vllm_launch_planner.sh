#!/usr/bin/env bash
# F.19.1a — Planner-role vLLM launcher.
#
# Serves qwen3-thinking-2507-awq (bench cell c08, ADR-009 §3) on :8502
# via native venv `vllm serve`. Matches the topology in ADR-009 §3a
# (dual-port + swap-on-demand supervisor). Only one of the coder or
# planner launcher should be running at a time; use ops/vllm_supervisor.sh
# to enforce that.
#
# Bench provenance:
#   bench/f19pre/vllm_launch.sh (Docker, c08 recipe) —
#     --reasoning-parser qwen3 --gpu-memory-utilization 0.90
#     --max-num-seqs 128 --max-model-len 32768 --dtype auto
#     (no --quantization flag; compressed-tensors autodetected)
#   bench/f19pre/results/scores_20260803.md — c08 scored 87/120,
#     only planner cell to complete any P3 answer.
#
# Blackwell / RTX 5090 (SM_120) notes:
#   * Weights ship as compressed-tensors — do NOT pass --quantization;
#     vLLM autodetects from config.json.quantization_config.
#   * --reasoning-parser qwen3 IS required — without it, chain-of-thought
#     tokens leak into `content` instead of `reasoning_content` and the
#     final answer looks like the c03 breakage.
#   * VLLM_USE_FLASHINFER_SAMPLER=0 preserved from F.18 — FlashInfer's
#     SM whitelist rejects SM_120.
#
# Token budget (ADR-009 §3b):
#   Planner max_completion_tokens = 8192 (set by the caller in the
#   LiteLLM llm block, not on the server; documented here for
#   discoverability). vLLM's --max-model-len 32768 already exceeds
#   this; do not lower it.
#
# Usage:
#   ./ops/vllm_launch_planner.sh                        # foreground
#   nohup ./ops/vllm_launch_planner.sh \
#     > ~/.forge-oh/vllm-planner.log 2>&1 &             # background
#
# Env overrides:
#   VLLM_PLANNER_PORT           default 8502
#   VLLM_PLANNER_MODEL_DIR      default ~/models/qwen3-thinking-2507-awq
#   VLLM_PLANNER_SERVED_NAME    default qwen3-thinking-2507-awq
#   VLLM_PLANNER_LOG            default ~/.forge-oh/vllm-planner.log
#   VLLM_VENV_BIN               default ~/venv/vllm-new/bin/vllm

# NOTE: no `set -e` at top level (per user preference — paste-block safe).

export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN

PORT="${VLLM_PLANNER_PORT:-8502}"
MODEL_DIR="${VLLM_PLANNER_MODEL_DIR:-$HOME/models/qwen3-thinking-2507-awq}"
SERVED_NAME="${VLLM_PLANNER_SERVED_NAME:-qwen3-thinking-2507-awq}"
LOG="${VLLM_PLANNER_LOG:-$HOME/.forge-oh/vllm-planner.log}"
VENV_BIN="${VLLM_VENV_BIN:-$HOME/venv/vllm-new/bin/vllm}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$(dirname "$LOG")"

# Clean any previous coder or planner instance so no ghost worker holds
# VRAM. The supervisor should have called this already, but we defend
# against direct invocation too.
if [ -x "$SCRIPT_DIR/vllm_stop_role.sh" ]; then
    "$SCRIPT_DIR/vllm_stop_role.sh" both || true
elif [ -x "$SCRIPT_DIR/../scripts/vllm_stop.sh" ]; then
    "$SCRIPT_DIR/../scripts/vllm_stop.sh" 8501 || true
    "$SCRIPT_DIR/../scripts/vllm_stop.sh" "$PORT" || true
else
    fuser -k "8501/tcp" 2>/dev/null || true
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    pkill -9 -f 'VLLM::EngineCore' 2>/dev/null || true
    pkill -9 -f 'vllm serve' 2>/dev/null || true
    sleep 2
fi

# Sanity: weights and venv must exist.
if [ ! -d "$MODEL_DIR" ]; then
    echo "planner weights not found at $MODEL_DIR" >&2
    echo "hint: symlink or download qwen3-thinking-2507-awq to that path" >&2
    exit 1
fi
if [ ! -x "$VENV_BIN" ]; then
    echo "vLLM binary not found at $VENV_BIN" >&2
    exit 1
fi

# 32GB Blackwell VRAM, ~30 GiB usable at 0.90 util. AWQ weights ~18-19 GiB
# leaves KV headroom for 32K context at max-num-seqs 128.
exec "$VENV_BIN" serve "$MODEL_DIR" \
    --served-model-name "$SERVED_NAME" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --gpu-memory-utilization 0.90 \
    --max-model-len 32768 \
    --max-num-seqs 128 \
    --dtype auto \
    --reasoning-parser qwen3 \
    --enable-prefix-caching \
    --trust-remote-code
