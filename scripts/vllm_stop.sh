#!/usr/bin/env bash
# vLLM stopper — atomically kills the APIServer + EngineCore workers +
# multiprocessing tracker so no ghost process holds VRAM.
#
# Ollama's `systemctl stop` does not release VRAM either, and vLLM leaves
# multiprocessing children behind when the parent dies. This script cleans
# both up.
#
# Usage: ./scripts/vllm_stop.sh [PORT]
set -uo pipefail

PORT="${1:-${VLLM_PORT:-8500}}"

echo "[vllm_stop] Stopping vLLM on port $PORT"

# 1. Free the TCP port (kills APIServer).
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null || true
fi

# 2. Kill any lingering EngineCore workers.
pkill -9 -f 'VLLM::EngineCore' 2>/dev/null || true

# 3. Kill the top-level `vllm serve` process if it's still around.
pkill -9 -f 'vllm serve' 2>/dev/null || true

# 4. Kill the multiprocessing resource tracker, which sometimes lingers
#    after EngineCore workers die and holds shared memory / CUDA context.
pkill -9 -f 'multiprocessing.resource_tracker' 2>/dev/null || true

# Give the kernel a moment to reap and release VRAM.
sleep 2

# 5. Report residuals so callers can decide whether to retry.
ENGINE_LEFT=$(pgrep -f 'VLLM::EngineCore' 2>/dev/null | wc -l)
SERVE_LEFT=$(pgrep -f 'vllm serve' 2>/dev/null | wc -l)
PORT_LEFT=$(ss -tln 2>/dev/null | grep -c ":${PORT}\b")

if [ "$ENGINE_LEFT" -eq 0 ] && [ "$SERVE_LEFT" -eq 0 ] && [ "$PORT_LEFT" -eq 0 ]; then
    echo "[vllm_stop] clean: no residual processes, port ${PORT} free"
    exit 0
fi

echo "[vllm_stop] residuals detected — EngineCore=$ENGINE_LEFT serve=$SERVE_LEFT port_${PORT}=$PORT_LEFT" >&2
exit 1
