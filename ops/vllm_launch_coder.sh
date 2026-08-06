#!/usr/bin/env bash
# F.19 coder-role vLLM launcher (Docker; matches bench/f19pre/vllm_launch.sh).
#
# ADR-013 amendment #1 (2026-08-05 04:55 EDT): default flipped to Qwen3.6-27B
# INT4 AutoRound after F.1b instrumented rebench. Ratified via unanimous
# 3-scorer Council pass. See docs/adr/013-qwen36-27b-canonical-coder-planner.md.
#
# Stage 8 Slice 8.0 (2026-08-06 15:30 EDT): serving-infra config bundle added.
# Verified vLLM 0.26.0 in vllm/vllm-openai:latest (>= 0.10 required for
# --long-prefill-token-threshold and --speculative-config JSON syntax).
#   * --kv-cache-dtype fp8            (halves KV memory, enables 65k ceiling)
#   * --max-model-len 32768 -> 65536  (closes 4 context-budget-skip tasks per
#                                     KNOWN_ISSUES §68)
#   * --enable-chunked-prefill        (long-prompt / decode co-scheduling)
#   * --long-prefill-token-threshold 4096 (chunk prompts > 4k)
#
# Ablated 2026-08-06 (Slice 8.0 DoD regression triage):
#   * --speculative-config ngram was removed after Step 1 smoke went
#     pass@1 33.3% -> 0/26. Malformed diff headers on the same tasks
#     (e.g. "+++ b/django/contrib/auth/" - filename truncated).
#     N-gram draft mis-acceptance on low-entropy structural tokens is
#     the working hypothesis. Re-enable only after a smoke matches
#     baseline pass@1 with the flag re-added. See DEBUG_LOG 2026-08-06.
# VRAM math: F.3 peak = 32,599 MiB @ concurrency=1. fp8 KV halves per-token
# to 80 KiB; 65536 * 80 KiB = 5.0 GiB per active seq — identical footprint
# to prior 32k*fp16 config. Raised ceiling is VRAM-neutral at concurrency=1.
# See docs/reconciliation-plan-stage-8.md §8.0 for full rationale.
#
# Serves qwen3.6-27b-int4-autoround on :8501 as "qwen3.6-27b-int4-autoround".
#
# The Lorbus/Qwen3.6-27B-int4-AutoRound weights are packaged as compressed-
# tensors int4; vLLM auto-detects the quant method from config.json — do NOT
# pass --quantization here. Tool-call parser matches Qwen3-Coder family.
#
# Native venv (~/venv/vllm-new, vLLM 0.10.2) does NOT support qwen3_5_moe.
# ADR-009 §5 requires vLLM ≥ 0.26.0 → we run the pinned Docker image the
# bench validated. Native venv upgrade is deferred to F.19.5.
#
# Env overrides:
#   FORGE_COMPOSE_MODELS_DIR   host dir mounted as /models (default $HOME/models)
#   FORGE_VLLM_IMAGE           docker image (default vllm/vllm-openai:latest)
#   FORGE_VLLM_CODER_PORT      host port (default 8501)
#   FORGE_VLLM_CODER_NAME      served-model-name / container tag (default qwen3.6-27b-int4-autoround)
#   FORGE_VLLM_CODER_MODEL_DIR model dir under /models (default qwen3.6-27b-int4-autoround)
#
# Rollback to ADR-009 baseline (qwen3.6-35b-nvfp4):
#   FORGE_VLLM_CODER_NAME=qwen3.6-35b-nvfp4 \
#   FORGE_VLLM_CODER_MODEL_DIR=qwen3.6-35b-nvfp4 \
#     bash ops/vllm_launch_coder.sh --quantization modelopt_fp4

MODELS_DIR="${FORGE_COMPOSE_MODELS_DIR:-$HOME/models}"
IMAGE="${FORGE_VLLM_IMAGE:-vllm/vllm-openai:latest}"
PORT="${FORGE_VLLM_CODER_PORT:-8501}"
NAME="${FORGE_VLLM_CODER_NAME:-qwen3.6-27b-int4-autoround}"
MODEL_DIR="${FORGE_VLLM_CODER_MODEL_DIR:-qwen3.6-27b-int4-autoround}"
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
  --max-model-len 65536 \
  --max-num-seqs 128 \
  --dtype auto \
  --trust-remote-code \
  --tool-call-parser qwen3_coder \
  --enable-auto-tool-choice \
  --enable-prefix-caching \
  --kv-cache-dtype fp8 \
  --enable-chunked-prefill \
  --long-prefill-token-threshold 4096 \
  "$@"
RC=$?
if [ $RC -ne 0 ]; then
  echo "[coder] docker run exited $RC" >&2
  exit $RC
fi
echo "[coder] container $CONTAINER launched; tail with: docker logs -f $CONTAINER"
