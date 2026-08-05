#!/usr/bin/env bash
# Planner-role vLLM launcher.
#
# ADR-013 (2026-08-05): default flipped to DSR1-Distill-Qwen-32B AWQ
# (casperhansen/deepseek-r1-distill-qwen-32b-awq) after Path E bench.
# Beat qwen3-thinking-2507-awq (ADR-009 default) within 3-point tie
# window and ~4x faster (15.5s vs 60.8s plan latency).
#
# Rollback: set FORGE_VLLM_PLANNER_MODEL_DIR=qwen3-thinking-2507-awq
# and FORGE_VLLM_PLANNER_REASONING_PARSER=qwen3 and
# FORGE_VLLM_PLANNER_QUANTIZATION='' (compressed-tensors autodetect).
#
# Native venv (~/venv/vllm-new, vLLM 0.10.2) does NOT support qwen3_5_moe.
# ADR-009 §5 requires vLLM ≥ 0.26.0 → we run the pinned Docker image the
# bench validated. Native venv upgrade is deferred to F.19.5.
#
# Env overrides:
#   FORGE_COMPOSE_MODELS_DIR             host dir mounted as /models (default $HOME/models)
#   FORGE_VLLM_IMAGE                     docker image (default vllm/vllm-openai:latest)
#   FORGE_VLLM_PLANNER_PORT              host port (default 8511)
#   FORGE_VLLM_PLANNER_NAME              served-model-name / container tag
#   FORGE_VLLM_PLANNER_MODEL_DIR         model dir under /models
#   FORGE_VLLM_PLANNER_REASONING_PARSER  reasoning parser (default deepseek_r1)
#   FORGE_VLLM_PLANNER_QUANTIZATION      quantization flag (default awq_marlin; empty=autodetect)

MODELS_DIR="${FORGE_COMPOSE_MODELS_DIR:-$HOME/models}"
IMAGE="${FORGE_VLLM_IMAGE:-vllm/vllm-openai:latest}"
PORT="${FORGE_VLLM_PLANNER_PORT:-8511}"
NAME="${FORGE_VLLM_PLANNER_NAME:-deepseek-r1-distill-32b-awq}"
MODEL_DIR="${FORGE_VLLM_PLANNER_MODEL_DIR:-deepseek-r1-distill-qwen-32b-awq}"
REASONING_PARSER="${FORGE_VLLM_PLANNER_REASONING_PARSER:-deepseek_r1}"
QUANTIZATION="${FORGE_VLLM_PLANNER_QUANTIZATION:-awq_marlin}"
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

echo "[planner] docker run $IMAGE -> :$PORT (model=$MODEL_DIR served-as=$NAME quant=${QUANTIZATION:-autodetect} parser=$REASONING_PARSER)"

# Assemble docker run args. --quantization is only added if set (empty = autodetect).
DOCKER_ARGS=(
  -d --name "$CONTAINER" --gpus all
  --ipc=host --shm-size=8g
  "${BLACKWELL_ENVS[@]}"
  -v "$MODELS_DIR:/models:ro"
  -p "${PORT}:8000"
  "$IMAGE"
  --model "/models/$MODEL_DIR"
  --served-model-name "$NAME"
  --host 0.0.0.0 --port 8000
  --gpu-memory-utilization 0.90
  --max-model-len 32768
  --max-num-seqs 128
  --dtype auto
  --trust-remote-code
  --reasoning-parser "$REASONING_PARSER"
  --enable-prefix-caching
)
if [ -n "$QUANTIZATION" ]; then
  DOCKER_ARGS+=(--quantization "$QUANTIZATION")
fi

docker run "${DOCKER_ARGS[@]}" "$@"
RC=$?
if [ $RC -ne 0 ]; then
  echo "[planner] docker run exited $RC" >&2
  exit $RC
fi
echo "[planner] container $CONTAINER launched; tail with: docker logs -f $CONTAINER"
