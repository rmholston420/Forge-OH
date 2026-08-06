#!/usr/bin/env bash
# Read-only follow-up probe. Decides between Fix A (redirect BFF to :8000)
# vs Fix B (stop container, use scripts/vllm_start.sh to bind :8501).

set +e

echo "=== A. What model is loaded on the running :8000 container? ==="
curl -sf --max-time 3 http://localhost:8000/v1/models | python3 -m json.tool | head -30
echo

echo "=== B. Full docker run command that started vllm-bench ==="
docker inspect vllm-bench --format '{{.Config.Cmd}}' 2>/dev/null
echo "--- entrypoint ---"
docker inspect vllm-bench --format '{{.Config.Entrypoint}}' 2>/dev/null
echo "--- env (filtered) ---"
docker inspect vllm-bench --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -Ei "HF_|MODEL|CUDA|SERVED" | head -10
echo

echo "=== C. scripts/vllm_start.sh contents ==="
cat ~/dev/forge-oh/scripts/vllm_start.sh 2>/dev/null
echo

echo "=== D. scripts/vllm_status.sh contents ==="
cat ~/dev/forge-oh/scripts/vllm_status.sh 2>/dev/null
echo

echo "=== E. scripts/vllm_stop.sh contents ==="
cat ~/dev/forge-oh/scripts/vllm_stop.sh 2>/dev/null
echo

echo "=== F. Model router expectation (what model does BFF think coder is?) ==="
grep -A2 "qwen3.6-27b-int4-autoround\|CODER_MODEL\|coder_model" ~/dev/forge-oh/bff/services/model_router.py 2>/dev/null | head -20
echo

echo "=== G. Any local env override for LLM_CODER_URL? ==="
grep -RIn "LLM_CODER_URL\|LLM_PLANNER_URL" ~/dev/forge-oh/.env* ~/dev/forge-oh/bff/.env* 2>/dev/null | head -5 || echo "  no .env override found"
