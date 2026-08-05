#!/bin/bash
# Teardown: stop vllm-bench, restart Ollama.
set -euo pipefail
docker rm -f vllm-bench 2>/dev/null || true
sudo systemctl start ollama 2>/dev/null || (ollama serve >/tmp/ollama.log 2>&1 &)
sleep 3
echo "vllm-bench stopped, Ollama restarted."
