#!/usr/bin/env bash
# Probe current vLLM/Ollama/GPU state on Colossus so we know what
# to bring back up. Read-only — makes no changes.

echo "=== 1. vLLM containers (any state) ==="
docker ps -a --filter "ancestor=vllm/vllm-openai" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Command}}' 2>/dev/null | head -20
echo

echo "=== 2. All :85xx listeners (BFF expects coder at 8501) ==="
ss -tlnp 2>/dev/null | grep -E ':(8500|8501|8511)\b' || echo "  none of 8500/8501/8511 listening"
echo

echo "=== 3. :8000 listener (vLLM Docker default port) ==="
ss -tlnp 2>/dev/null | grep ':8000\b' || echo "  nothing on 8000"
echo

echo "=== 4. Ollama status ==="
systemctl is-active ollama 2>/dev/null && echo "  systemd unit: active" || echo "  systemd unit: inactive/missing"
if curl -sf --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "  :11434 responding"
  curl -s http://localhost:11434/api/tags | python3 -c "import json, sys; d=json.load(sys.stdin); print('  models:', [m['name'] for m in d.get('models',[])][:10])" 2>/dev/null
else
  echo "  :11434 NOT responding"
fi
echo

echo "=== 5. GPU ==="
nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader 2>/dev/null || echo "  nvidia-smi failed"
echo

echo "=== 6. Any process holding the GPU ==="
sudo fuser -v /dev/nvidia* 2>&1 | head -20 || nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null
echo

echo "=== 7. BFF vLLM supervisor references (which port does it dial?) ==="
grep -RIn "8501\|8511\|vllm-coder\|vllm_coder" ~/dev/forge-oh/bff/ 2>/dev/null | grep -v ".pyc\|__pycache__" | head -20
echo

echo "=== 8. vLLM supervisor script/service (if any) ==="
ls -la ~/bin/vllm* ~/dev/forge-oh/scripts/vllm* /etc/systemd/system/vllm* 2>/dev/null | grep -v "cannot access" || echo "  no obvious supervisor script/service found"
echo

echo "=== 9. Recent vLLM logs ==="
ls -lat ~/.forge-oh/*.log ~/logs/vllm* /tmp/vllm* 2>/dev/null | head -5 || echo "  no obvious vllm log files"
