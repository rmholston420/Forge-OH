#!/bin/bash
# Path E vLLM launcher — one cell at a time on Colossus (RTX 5090, 32 GB VRAM).
#
# Usage:
#   vllm_launch.sh <cell_id>
#
# Cells:
#   c01  = Qwen3.6-27B AutoRound INT4       (coder,   proposed)
#   c02  = Qwen3.6-35B-A3B NVFP4            (coder,   ADR-009 baseline)
#   c03b = Qwen3-Coder-30B-A3B AWQ-4bit     (coder,   specialized-coder quality upgrade over c03 Q4_K_M)
#   c04  = Qwen3.6-27B NVFP4                (planner, proposed)
#   c05  = Qwen3-Thinking-2507 AWQ           (planner, ADR-009 baseline)
#
# Requires the following model dirs under ~/models/ (HuggingFace weights):
#   qwen3.6-27b-int4-autoround/        (Lorbus/Qwen3.6-27B-int4-AutoRound)
#   qwen3.6-35b-nvfp4/                 (RedHatAI/Qwen3.6-35B-A3B-NVFP4, existing on Colossus)
#   qwen3.6-27b-nvfp4/                 (nvidia/Qwen3.6-27B-NVFP4)
#   qwen3-thinking-2507-awq/           (existing, per ADR-009)
#
# The script stops Ollama (to free VRAM), removes any prior vllm-bench
# container, launches the requested cell, and waits for readiness.

set -euo pipefail

CELL="${1:?usage: $0 <c01|c02|c03b|c04|c05>}"

ts()   { date '+%Y-%m-%d %H:%M:%S %Z'; }
ts_s() { date +%s; }
T0=$(ts_s)
echo "[$(ts)] vllm_launch.sh start (cell=$CELL)"

# Free VRAM before vLLM launch (both Ollama and any prior vLLM container)
sudo systemctl stop ollama 2>/dev/null || pkill -x ollama 2>/dev/null || true
docker rm -f vllm-bench 2>/dev/null || true
sleep 3

# Verify GPU is idle before launching (guards against orphaned engines)
BUSY_MIB=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
if [ "${BUSY_MIB:-0}" -gt 2000 ]; then
  echo "WARN: GPU has ${BUSY_MIB} MiB used before launch (expected < 2000 MiB)" >&2
  echo "      processes still holding VRAM:" >&2
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv >&2
  echo "      continue anyway? Ctrl-C within 10s to abort." >&2
  sleep 10
fi

case "$CELL" in
  c01)
    MODEL_DIR="qwen3.6-27b-int4-autoround"
    SERVED_NAME="c01_coder_vllm_qwen36_27b_int4"
    EXTRA_FLAGS=(
      --tool-call-parser qwen3_coder
      --enable-auto-tool-choice
    )
    ;;
  c02)
    MODEL_DIR="qwen3.6-35b-nvfp4"
    SERVED_NAME="c02_coder_vllm_qwen36_35b_nvfp4"
    EXTRA_FLAGS=(
      --quantization modelopt_fp4
      --tool-call-parser qwen3_coder
      --enable-auto-tool-choice
    )
    ;;
  c03b)
    # Despite the "AWQ-4bit" in the repo name, cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit
    # is packaged as compressed-tensors int4 (pack-quantized, group_size=32, symmetric).
    # vLLM auto-detects the quant method from config.json — do NOT pass --quantization.
    # See DEBUG_LOG 2026-08-05 00:00 EDT.
    MODEL_DIR="Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
    SERVED_NAME="c03b_coder_vllm_qwen3coder_awq"
    EXTRA_FLAGS=(
      --tool-call-parser qwen3_coder
      --enable-auto-tool-choice
    )
    ;;
  c04)
    # Qwen3.6-27B uses Mamba/hybrid attention: fixed Mamba cache slots (~111 on 32GB w/ 0.90 util).
    # Each parallel decode sequence consumes one slot, so max_num_seqs must be <= slots.
    # See DEBUG_LOG 2026-08-04 23:57 EDT — c04 first attempt with max_num_seqs=128 failed.
    MODEL_DIR="qwen3.6-27b-nvfp4"
    SERVED_NAME="c04_planner_vllm_qwen36_27b_nvfp4"
    MAX_NUM_SEQS=96
    EXTRA_FLAGS=(
      --quantization modelopt_fp4
      --reasoning-parser qwen3
    )
    ;;
  c05)
    MODEL_DIR="qwen3-thinking-2507-awq"
    SERVED_NAME="c05_planner_vllm_qwen3thinking_awq"
    EXTRA_FLAGS=(
      --reasoning-parser qwen3
    )
    ;;
  *)
    echo "unknown cell: $CELL (valid: c01 c02 c03b c04 c05)" >&2
    exit 2
    ;;
esac

if [ ! -d "$HOME/models/$MODEL_DIR" ]; then
  echo "ERROR: model dir not found: $HOME/models/$MODEL_DIR" >&2
  echo "Pull the model first — see bench/pathE_qwen36_27b/pull_models.sh" >&2
  exit 3
fi

echo "[$(ts)] → launching $CELL: $MODEL_DIR as $SERVED_NAME"

docker run -d --name vllm-bench --gpus all \
  --ipc=host --shm-size=8g \
  -v "$HOME/models:/models:ro" \
  -p 8000:8000 \
  -e HF_HUB_OFFLINE=1 \
  vllm/vllm-openai:latest \
  --model "/models/$MODEL_DIR" \
  --served-model-name "$SERVED_NAME" \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --max-num-seqs "${MAX_NUM_SEQS:-128}" \
  --kv-cache-dtype fp8 \
  --dtype auto \
  --trust-remote-code \
  "${EXTRA_FLAGS[@]}"

T_LAUNCH=$(ts_s)
echo "[$(ts)] → container launched; waiting for /v1/models (up to 900s)"
for i in $(seq 1 450); do
  if curl -sf http://localhost:8000/v1/models >/dev/null 2>&1; then
    ELAPSED=$(( $(ts_s) - T_LAUNCH ))
    TOTAL=$(( $(ts_s) - T0 ))
    echo "[$(ts)] READY (${ELAPSED}s wait, ${TOTAL}s total)"
    curl -s http://localhost:8000/v1/models | python3 -m json.tool
    exit 0
  fi
  sleep 2
done

echo "[$(ts)] ERROR: vllm-bench did not become ready within 900s. docker logs --tail 80 vllm-bench:" >&2
docker logs --tail 80 vllm-bench >&2
exit 1
