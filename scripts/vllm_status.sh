#!/usr/bin/env bash
# vLLM status — reports true state (APIServer + EngineCore + port + /v1/models).
#
# A vLLM instance is only "healthy" when ALL of the following hold:
#   - `VLLM::EngineCore` process is alive
#   - Port is listening
#   - `/v1/models` returns 200 (i.e. weight load has finished)
#
# Otherwise it's in one of several broken states we've seen: EngineCore ghost
# without APIServer, APIServer with dead EngineCore, or still loading weights.
#
# Usage: ./scripts/vllm_status.sh [PORT]
# Exit codes: 0=healthy, 1=broken, 2=loading, 3=absent

set -uo pipefail

PORT="${1:-${VLLM_PORT:-8500}}"
URL="${VLLM_URL:-http://127.0.0.1:${PORT}}"

ENGINE=$(pgrep -f 'VLLM::EngineCore' 2>/dev/null | wc -l)
SERVE=$(pgrep -f 'vllm serve' 2>/dev/null | wc -l)
LISTENING=$(ss -tln 2>/dev/null | grep -c ":${PORT}\b")

# HTTP probe
if curl -sf --max-time 3 "${URL}/v1/models" >/dev/null 2>&1; then
    HTTP_OK=1
else
    HTTP_OK=0
fi

echo "vllm_status:"
echo "  EngineCore workers : $ENGINE"
echo "  'vllm serve' procs : $SERVE"
echo "  Port $PORT listening   : $LISTENING"
echo "  ${URL}/v1/models OK: $HTTP_OK"

if [ "$ENGINE" -eq 0 ] && [ "$SERVE" -eq 0 ] && [ "$LISTENING" -eq 0 ]; then
    echo "state: absent"
    exit 3
fi

if [ "$HTTP_OK" -eq 1 ] && [ "$ENGINE" -ge 1 ]; then
    echo "state: healthy"
    exit 0
fi

if [ "$ENGINE" -ge 1 ] && [ "$LISTENING" -ge 1 ] && [ "$HTTP_OK" -eq 0 ]; then
    echo "state: loading"
    exit 2
fi

echo "state: broken"
exit 1
