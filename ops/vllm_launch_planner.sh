#!/usr/bin/env bash
# F.19 planner-role vLLM launcher (Docker; matches bench/f19pre/vllm_launch.sh).
#
# Serves qwen3-thinking-2507-awq on :8502 as "qwen3-thinking-2507-awq".
#
# Native venv (~/venv/vllm-new, vLLM 0.10.2) does NOT support qwen3_5_moe.
# ADR-009 §5 requires vLLM ≥ 0.26.0 → we run the pinned Docker image the
# bench validated. Native venv upgrade is deferred to F.19.5.
#
# Env overrides:
#   FORGE_COMPOSE_MODELS_DIR     host dir mounted as /models (default $HOME/models)
#   FORGE_VLLM_IMAGE             docker image (default vllm/vllm-openai:latest)
#   FORGE_VLLM_PLANNER_PORT      host port (default 8502)
#   FORGE_VLLM_PLANNER_NAME      served-model-name / container tag
#   FORGE_VLLM_PLANNER_MODEL_DIR model dir under /models

MODELS_DIR="${FORGE_COMPOSE_MODELS_DIR:-$HOME/models}"
IMAGE="${FORGE_VLLM_IMAGE:-vllm/vllm-openai:latest}"
PORT="${FORGE_VLLM_PLANNER_PORT:-8502}"
NAME="${FORGE_VLLM_PLANNER_NAME:-qwen3-thinking-2507-awq}"
MODEL_DIR="${FORGE_VLLM_PLANNER_MODEL_DIR:-qwen3-thinking-2507-awq}"
CONTAINER="forge-vllm-planner"

if [ ! -d "$MODELS_DIR/$MODEL_DIR" ]; then
  echo "[planner] ERROR: weights not found at $MODELS_DIR/$MODEL_DIR" >&2
  exit 2
fi

BLACKWELL_ENVS=(
  -e VLLM_USE_FLASHINFER_SAMPLER=0
  -e VLLM_ATTENTION_BACKEND=FLASH_ATTN
  -e HF_HUB_OFFLINE=1
)

docker rm -f "$CONTAINER" 2>/dev/null || true

echo "[planner] docker run $IMAGE -> :$PORT (model=$MODEL_DIR served-as=$NAME)"
# compressed-tensors AWQ is autodetected by vLLM 0.26+, no --quantization flag.
docker run -d --name "$CONTAINER" --gpus all \
  --ipc=host --shm-size=8g \
  "${BLACKWELL_ENVS[@]}" \
  -v "$MODELS_DIR:/models:ro" \
  -p "${PORT}:8000" \
  "$IMAGE" \
  --model "/models/$MODEL_DIR" \
  --served-model-name "$NAME" \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --max-num-seqs 128 \
  --dtype auto \
  --trust-remote-code \
  --reasoning-parser qwen3 \
  --enable-prefix-caching \
  "$@"
RC=$?
if [ $RC -ne 0 ]; then
  echo "[planner] docker run exited $RC" >&2
  exit $RC
fi
echo "[planner] container $CONTAINER launched; tail with: docker logs -f $CONTAINER"
