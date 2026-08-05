#!/bin/bash
# Path E vLLM launcher — one cell at a time on Colossus (RTX 5090, 32 GB VRAM).
#
# Usage:
#   vllm_launch.sh <cell_id>
#
# Cells:
#   c01 = Qwen3.6-27B AutoRound INT4        (coder,   proposed)
#   c02 = Qwen3.6-35B-A3B NVFP4             (coder,   ADR-009 baseline)
#   c04 = Qwen3.6-27B NVFP4                 (planner, proposed)
#   c05 = Qwen3-Thinking-2507 AWQ            (planner, ADR-009 baseline)
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

CELL="${1:?usage: $0 <c01|c02|c04|c05>}"

# Free VRAM before vLLM launch
sudo systemctl stop ollama 2>/dev/null || pkill -x ollama 2>/dev/null || true
sleep 3
docker rm -f vllm-bench 2>/dev/null || true

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
  c04)
    MODEL_DIR="qwen3.6-27b-nvfp4"
    SERVED_NAME="c04_planner_vllm_qwen36_27b_nvfp4"
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
    echo "unknown cell: $CELL (valid: c01 c02 c04 c05)" >&2
    exit 2
    ;;
esac

if [ ! -d "$HOME/models/$MODEL_DIR" ]; then
  echo "ERROR: model dir not found: $HOME/models/$MODEL_DIR" >&2
  echo "Pull the model first — see bench/pathE_qwen36_27b/pull_models.sh" >&2
  exit 3
fi

echo "→ launching $CELL: $MODEL_DIR as $SERVED_NAME"

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
  --max-num-seqs 128 \
  --kv-cache-dtype fp8 \
  --dtype auto \
  --trust-remote-code \
  "${EXTRA_FLAGS[@]}"

echo "→ waiting for readiness (up to 300s)..."
for i in $(seq 1 150); do
  if curl -sf http://localhost:8000/v1/models >/dev/null 2>&1; then
    echo "READY (${i}0s elapsed)"
    curl -s http://localhost:8000/v1/models | python3 -m json.tool
    exit 0
  fi
  sleep 2
done

echo "ERROR: vllm-bench did not become ready within 300s. docker logs --tail 60 vllm-bench:" >&2
docker logs --tail 60 vllm-bench >&2
exit 1
