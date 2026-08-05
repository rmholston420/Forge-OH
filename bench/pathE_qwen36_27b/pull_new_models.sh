#!/bin/bash
# Pull new coder/planner models for F.19-post expansion.
#
# Downloads (~104 GB total; ~517 GB free on Colossus as of 2026-08-05):
#   c07  Qwen3-Coder-30B-A3B-Instruct-FP8           (~29 GB, official Qwen)
#   c09  Codestral-22B-v0.1-AWQ                     (~12 GB, TechxGenus)
#   c10  Devstral-Small-2-24B-Instruct-2512-nvfp4   (~15 GB, Firworks)
#   c11  Devstral-Small-2-24B-Instruct-2512-AWQ-4bit (~30 GB, cyankiwi)
#   c12  deepseek-r1-distill-qwen-32b-awq           (~18 GB, casperhansen)
#
# c08 uses Ollama (no HF pull needed):
#   ollama pull yi:34b-chat-v1.5-q4_K_M             (~19 GB via Ollama registry)
#
# Prerequisites (per colossus-python-env skill):
#   HF venv must be active. Recommended:
#     source ~/venv/vllm-new/bin/activate
#     pip install -U huggingface_hub
#     export HF_XET_HIGH_PERFORMANCE=1     # supersedes HF_HUB_ENABLE_HF_TRANSFER on hub>=1.0

set -euo pipefail

MODELS_DIR="$HOME/models"
mkdir -p "$MODELS_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

# Download the full snapshot. huggingface_hub 1.0+ has removed reliable
# --include/--exclude filtering from the CLI (both are silently ignored when
# positional filenames are also present, and positional filenames themselves
# are treated as literal names). Simplest correct behavior: pull everything,
# then rm GGUFs afterward if they exist.
pull() {
  local REPO="$1"
  local LOCAL="$2"
  local DIR="$MODELS_DIR/$LOCAL"
  # Sentinel for "weights actually downloaded": at least one non-empty *.safetensors
  local have_weights=0
  if [ -d "$DIR" ] && [ -f "$DIR/config.json" ]; then
    if find "$DIR" -maxdepth 2 -name '*.safetensors' -size +100M 2>/dev/null | grep -q .; then
      have_weights=1
    fi
  fi
  if [ "$have_weights" = "1" ]; then
    echo "[$(ts)] SKIP $LOCAL (weights already present at $DIR)"
    return 0
  fi
  echo "[$(ts)] PULL $REPO -> $DIR (full snapshot)"
  hf download "$REPO" --local-dir "$DIR"
  # Strip any GGUFs — vLLM does not use them and they inflate footprint.
  find "$DIR" -maxdepth 2 -name '*.gguf' -type f -print -delete 2>/dev/null || true
  # Verify at least one shard landed
  if ! find "$DIR" -maxdepth 2 -name '*.safetensors' -size +100M 2>/dev/null | grep -q .; then
    echo "[$(ts)] FAIL $LOCAL: no .safetensors > 100MB found under $DIR" >&2
    return 3
  fi
  echo "[$(ts)] DONE $LOCAL"
}

# Prefer new xet high-performance transfer if this hub version supports it,
# but tolerate either env var (older hub versions still honor HF_HUB_ENABLE_HF_TRANSFER).
: "${HF_XET_HIGH_PERFORMANCE:=${HF_HUB_ENABLE_HF_TRANSFER:-1}}"
export HF_XET_HIGH_PERFORMANCE

pull "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"                          "Qwen3-Coder-30B-A3B-Instruct-FP8"
pull "TechxGenus/Codestral-22B-v0.1-AWQ"                              "Codestral-22B-v0.1-AWQ"
pull "Firworks/Devstral-Small-2-24B-Instruct-2512-nvfp4"              "Devstral-Small-2-24B-Instruct-2512-nvfp4"
pull "cyankiwi/Devstral-Small-2-24B-Instruct-2512-AWQ-4bit"           "Devstral-Small-2-24B-Instruct-2512-AWQ-4bit"
pull "casperhansen/deepseek-r1-distill-qwen-32b-awq"                  "deepseek-r1-distill-qwen-32b-awq"

echo ""
echo "[$(ts)] All HF pulls complete."
echo "[$(ts)] For c08, also run:  ollama pull yi:34b-chat-v1.5-q4_K_M"

# Disk check
df -h "$MODELS_DIR" | tail -1
