#!/bin/bash
# Usage: vllm_launch.sh <model_dir_name> <served_name> [extra_vllm_flags...]
# Example: vllm_launch.sh qwen3-coder-30b-awq c02_coder_vllm_qwen3coder_awq
# Example: vllm_launch.sh qwen3.6-35b-nvfp4 c04_coder_vllm_qwen36_nvfp4 --quantization modelopt_fp4
# Example: vllm_launch.sh qwen3.6-35b-nvfp4 c06_planner_vllm_qwen36_nvfp4 --quantization modelopt_fp4 --reasoning-parser qwen3
# Example: vllm_launch.sh qwen3-thinking-2507-awq c08_planner_vllm_thinking_awq --reasoning-parser qwen3
set -e
MODEL_DIR="$1"; SERVED_NAME="$2"; shift 2 || { echo "usage: $0 <model_dir> <served_name> [flags...]"; exit 2; }
docker rm -f vllm-bench 2>/dev/null || true
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
  --dtype auto \
  --trust-remote-code \
  "$@"
echo "launched vllm-bench: $MODEL_DIR as $SERVED_NAME"
echo "wait for readiness then curl http://localhost:8000/v1/models"
