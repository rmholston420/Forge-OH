#!/usr/bin/env bash
# Probe the actual running BFF process env + any dotfiles.
# Read-only.

set +e

echo "=== 1. BFF process command line + env (via /proc) ==="
BFF_PID="$(pgrep -f 'uvicorn.*bff\.main' | head -1)"
echo "BFF pid: $BFF_PID"
if [[ -n "$BFF_PID" ]]; then
  echo "--- cmdline ---"
  tr '\0' ' ' < "/proc/$BFF_PID/cmdline"; echo
  echo "--- LLM_ env from /proc/$BFF_PID/environ ---"
  tr '\0' '\n' < "/proc/$BFF_PID/environ" | grep -E "^LLM_|^FORGE_|^OLLAMA_|^VLLM_" | sort
  echo "--- start time ---"
  ps -o pid,lstart,cmd -p "$BFF_PID"
fi
echo

echo "=== 2. All BFF processes (in case forge-up.sh started another one) ==="
pgrep -af 'uvicorn.*bff\.main' || echo "  none"
echo

echo "=== 3. Every uvicorn-ish process ==="
pgrep -af 'uvicorn' | head -10 || echo "  none"
echo

echo "=== 4. forge-up.sh content (does it re-export env or re-launch bff?) ==="
grep -nE "uvicorn|LLM_|env|BFF" ~/dev/forge-oh/scripts/forge-up.sh 2>/dev/null | head -30
echo

echo "=== 5. Any .env file the BFF might load ==="
ls -la ~/dev/forge-oh/.env* ~/dev/forge-oh/bff/.env* ~/dev/forge-oh/bff/*.env 2>/dev/null | grep -v "cannot access"
echo

echo "=== 6. Does bff.main or model_router load dotenv? ==="
grep -RIn "dotenv\|load_dotenv\|from_env\|\.env" ~/dev/forge-oh/bff/main.py ~/dev/forge-oh/bff/services/model_router.py ~/dev/forge-oh/bff/services/inference_backends/ 2>/dev/null | head -10
echo

echo "=== 7. Test the URL directly from BFF's POV ==="
curl -sf --max-time 3 http://localhost:8501/v1/models >/dev/null 2>&1 && echo ":8501 responding" || echo ":8501 NOT responding (as expected)"
curl -sf --max-time 3 http://localhost:8000/v1/models >/dev/null 2>&1 && echo ":8000 responding" || echo ":8000 NOT responding"
echo

echo "=== 8. Any recent log lines mentioning LLM_CODER_URL or 8501 ==="
tail -50 ~/.forge-oh/bff.log 2>/dev/null | grep -Ei "coder|8501|8000|vllm" | tail -10
