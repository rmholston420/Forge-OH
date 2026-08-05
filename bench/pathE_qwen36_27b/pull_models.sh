#!/bin/bash
# Path E — pull required model weights to ~/models/ for benching.
#
# Baseline models (c02, c03, c05) are assumed to already be present
# from prior ADR-009 / F.19-pre work on Colossus. This script pulls
# ONLY the two new models the bench is testing:
#
#   Lorbus/Qwen3.6-27B-int4-AutoRound   (c01, coder pick)
#   nvidia/Qwen3.6-27B-NVFP4            (c04, planner pick)
#
# Uses huggingface-cli which respects HF_HOME. The two models share
# nothing but their base name — download both fully.

set -euo pipefail

MODELS_DIR="$HOME/models"
mkdir -p "$MODELS_DIR"

# Activate the correct Colossus venv (per user-scope skill colossus-python-env)
# — the venv is expected to have `hf` (or huggingface-cli) available.
# Adjust VENV path if different on your workstation.
VENV="${VENV:-$HOME/.forge-oh/venv}"
if [ -f "$VENV/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
fi

# Prefer the new `hf` CLI (huggingface_hub >=0.28) if present, else fall back.
if command -v hf >/dev/null 2>&1; then
  DL="hf download"
elif command -v huggingface-cli >/dev/null 2>&1; then
  DL="huggingface-cli download"
else
  echo "ERROR: neither 'hf' nor 'huggingface-cli' found. Install huggingface_hub." >&2
  exit 2
fi

echo "→ using: $DL"
echo "→ MODELS_DIR: $MODELS_DIR"

# c01 coder pick — Lorbus AutoRound INT4
if [ ! -d "$MODELS_DIR/qwen3.6-27b-int4-autoround" ]; then
  echo "→ pulling Lorbus/Qwen3.6-27B-int4-AutoRound → qwen3.6-27b-int4-autoround/"
  $DL Lorbus/Qwen3.6-27B-int4-AutoRound \
    --local-dir "$MODELS_DIR/qwen3.6-27b-int4-autoround"
else
  echo "→ qwen3.6-27b-int4-autoround already present, skipping"
fi

# c04 planner pick — official NVIDIA NVFP4
if [ ! -d "$MODELS_DIR/qwen3.6-27b-nvfp4" ]; then
  echo "→ pulling nvidia/Qwen3.6-27B-NVFP4 → qwen3.6-27b-nvfp4/"
  $DL nvidia/Qwen3.6-27B-NVFP4 \
    --local-dir "$MODELS_DIR/qwen3.6-27b-nvfp4"
else
  echo "→ qwen3.6-27b-nvfp4 already present, skipping"
fi

echo ""
echo "→ done. Verify:"
ls -la "$MODELS_DIR" | grep qwen3.6-27b
echo ""
echo "→ if c02 (qwen3.6-35b-a3b-nvfp4), c03 (Ollama qwen3-coder:32k), or"
echo "  c05 (qwen3-thinking-2507-awq) are missing, pull them per ADR-009."
