#!/bin/bash
# Wait up to 300s for vLLM readiness. Prints READY on success, TIMEOUT on failure.
set -e
for i in $(seq 1 150); do
  if curl -sf http://localhost:8000/v1/models >/dev/null 2>&1; then
    echo "READY (${i}x2s)"
    curl -s http://localhost:8000/v1/models | python3 -c "import sys,json;d=json.load(sys.stdin);print('served:', d['data'][0]['id'])"
    exit 0
  fi
  sleep 2
done
echo "TIMEOUT after 300s"
docker logs --tail 50 vllm-bench
exit 1
