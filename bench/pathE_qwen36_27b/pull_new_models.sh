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
#   ollama pull yi-1.5:34b                          (~19 GB via Ollama registry)
#
# Prerequisites (per colossus-python-env skill):
#   HF venv must be active AND hf_transfer installed. Fastest recipe:
#     source ~/venv/vllm-new/bin/activate
#     pip install -U "huggingface_hub[cli]" hf_transfer
#     export HF_HUB_ENABLE_HF_TRANSFER=1

set -euo pipefail

MODELS_DIR="$HOME/models"
mkdir -p "$MODELS_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

pull() {
  local REPO="$1"
  local LOCAL="$2"
  local DIR="$MODELS_DIR/$LOCAL"
  if [ -d "$DIR" ] && [ -f "$DIR/config.json" ]; then
    echo "[$(ts)] SKIP $LOCAL (already at $DIR)"
    return 0
  fi
  echo "[$(ts)] PULL $REPO -> $DIR"
  hf download "$REPO" --local-dir "$DIR" --exclude "*.gguf" "original/*"
  echo "[$(ts)] DONE $LOCAL"
}

# Verify hf_transfer available if enabled
if [ "${HF_HUB_ENABLE_HF_TRANSFER:-0}" = "1" ]; then
  python -c "import hf_transfer" 2>/dev/null || {
    echo "ERROR: HF_HUB_ENABLE_HF_TRANSFER=1 but hf_transfer not importable in this venv." >&2
    echo "Fix: pip install hf_transfer   OR   unset HF_HUB_ENABLE_HF_TRANSFER" >&2
    exit 2
  }
fi

pull "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"                          "Qwen3-Coder-30B-A3B-Instruct-FP8"
pull "TechxGenus/Codestral-22B-v0.1-AWQ"                              "Codestral-22B-v0.1-AWQ"
pull "Firworks/Devstral-Small-2-24B-Instruct-2512-nvfp4"              "Devstral-Small-2-24B-Instruct-2512-nvfp4"
pull "cyankiwi/Devstral-Small-2-24B-Instruct-2512-AWQ-4bit"           "Devstral-Small-2-24B-Instruct-2512-AWQ-4bit"
pull "casperhansen/deepseek-r1-distill-qwen-32b-awq"                  "deepseek-r1-distill-qwen-32b-awq"

echo ""
echo "[$(ts)] All HF pulls complete."
echo "[$(ts)] For c08, also run:  ollama pull yi-1.5:34b"

# Disk check
df -h "$MODELS_DIR" | tail -1
