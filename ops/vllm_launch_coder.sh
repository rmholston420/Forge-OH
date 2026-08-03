#!/usr/bin/env bash
# F.19 coder-role vLLM launcher (Docker; matches bench/f19pre/vllm_launch.sh).
#
# Serves qwen3.6-35b-nvfp4 on :8501 as "qwen3.6-35b-nvfp4".
#
# Native venv (~/venv/vllm-new, vLLM 0.10.2) does NOT support qwen3_5_moe.
# ADR-009 §5 requires vLLM ≥ 0.26.0 → we run the pinned Docker image the
# bench validated. Native venv upgrade is deferred to F.19.5.
#
# Env overrides:
#   FORGE_COMPOSE_MODELS_DIR   host dir mounted as /models (default $HOME/models)
#   FORGE_VLLM_IMAGE           docker image (default vllm/vllm-openai:latest)
#   FORGE_VLLM_CODER_PORT      host port (default 8501)
#   FORGE_VLLM_CODER_NAME      served-model-name / container tag (default qwen3.6-35b-nvfp4)
#   FORGE_VLLM_CODER_MODEL_DIR model dir under /models (default qwen3.6-35b-nvfp4)

MODELS_DIR="${FORGE_COMPOSE_MODELS_DIR:-$HOME/models}"
IMAGE="${FORGE_VLLM_IMAGE:-vllm/vllm-openai:latest}"
PORT="${FORGE_VLLM_CODER_PORT:-8501}"
NAME="${FORGE_VLLM_CODER_NAME:-qwen3.6-35b-nvfp4}"
MODEL_DIR="${FORGE_VLLM_CODER_MODEL_DIR:-qwen3.6-35b-nvfp4}"
CONTAINER="forge-vllm-coder"

if [ ! -d "$MODELS_DIR/$MODEL_DIR" ]; then
  echo "[coder] ERROR: weights not found at $MODELS_DIR/$MODEL_DIR" >&2
  exit 2
fi

# Blackwell SM_120 operational env — carried through to container.
BLACKWELL_ENVS=(
  -e VLLM_USE_FLASHINFER_SAMPLER=0
  -e VLLM_ATTENTION_BACKEND=FLASH_ATTN
  -e HF_HUB_OFFLINE=1
)

docker rm -f "$CONTAINER" 2>/dev/null || true

echo "[coder] docker run $IMAGE -> :$PORT (model=$MODEL_DIR served-as=$NAME)"
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
  --quantization modelopt_fp4 \
  --enable-prefix-caching \
  "$@"
RC=$?
if [ $RC -ne 0 ]; then
  echo "[coder] docker run exited $RC" >&2
  exit $RC
fi
echo "[coder] container $CONTAINER launched; tail with: docker logs -f $CONTAINER"
