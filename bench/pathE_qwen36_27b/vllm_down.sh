#!/bin/bash
# Teardown: stop vllm-bench, restart Ollama.
set -euo pipefail
ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
T0=$(date +%s)
echo "[$(ts)] vllm_down.sh start"
docker rm -f vllm-bench 2>/dev/null || true
sudo systemctl start ollama 2>/dev/null || (ollama serve >/tmp/ollama.log 2>&1 &)
sleep 3
echo "[$(ts)] vllm-bench stopped, Ollama restarted ($(( $(date +%s) - T0 ))s)"
