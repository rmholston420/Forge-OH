#!/usr/bin/env bash
# Reconcile BFF with the already-running vLLM container.
#
# Situation observed 2026-08-06 07:37 EDT:
#   - Container ``vllm-bench`` is UP on :8000 with model
#     qwen3.6-27b-int4-autoround, served-name c01_coder_vllm_qwen36_27b_int4.
#   - BFF defaults to LLM_CODER_URL=http://localhost:8501 and
#     LLM_CODER_MODEL=qwen3.6-27b-int4-autoround.
#   - Two mismatches (port + served-name) mean the BFF sees "coder down".
#
# Fix: override both env vars, restart BFF, then verify /v1/models + a
# real POST /api/runs create succeeds against ap-1.

set -uo pipefail

FORGE_DIR="${FORGE_DIR:-$HOME/dev/forge-oh}"

# ─── 1. Sanity: container is actually up on :8000 ─────────────────

echo "→ Probing vLLM on :8000…"
if ! curl -sf --max-time 3 http://localhost:8000/v1/models >/dev/null; then
  echo "✗ Nothing on :8000. Aborting — this script assumes the vllm-bench" >&2
  echo "  container is already serving there. Fix the container first." >&2
  exit 1
fi

served_name="$(curl -s http://localhost:8000/v1/models | python3 -c "
import json, sys
d = json.load(sys.stdin)
print((d.get('data') or [{}])[0].get('id', ''))
")"
echo "→ :8000 is serving model id: $served_name"

if [[ -z "$served_name" ]]; then
  echo "✗ Could not extract served-model-name from /v1/models" >&2
  exit 1
fi

# ─── 2. Restart BFF with the two overrides ────────────────────────

cd "$FORGE_DIR"

echo "→ Bringing BFF down (forge-down.sh will reap orphan children)…"
bash scripts/forge-down.sh 2>&1 | tail -6

echo "→ Bringing BFF back up with LLM_CODER_URL=http://localhost:8000 and LLM_CODER_MODEL=$served_name…"

# We can't just re-run forge-up.sh — it doesn't take these overrides.
# Launch BFF directly with the env vars set.  Frontend + agent-server
# are separate concerns and forge-up.sh still owns them.
mkdir -p ~/.forge-oh
LLM_CODER_URL=http://localhost:8000 \
LLM_CODER_MODEL="$served_name" \
  nohup .oh-venv/bin/uvicorn bff.main:app_with_sio \
    --host 127.0.0.1 --port 8081 \
    > ~/.forge-oh/bff.log 2>&1 &
BFF_PID=$!
echo "$BFF_PID" > ~/.forge-oh/bff.pid
echo "→ BFF pid: $BFF_PID"

# Wait for BFF ready.
for i in $(seq 1 30); do
  if curl -sf --max-time 1 http://127.0.0.1:8081/api/health >/dev/null 2>&1 || \
     curl -sf --max-time 1 http://127.0.0.1:8081/api/agent-presets >/dev/null 2>&1; then
    echo "→ BFF ready after ${i}s"
    break
  fi
  sleep 1
done

# Start frontend + agent-server via canonical script (they're idempotent).
echo "→ Starting the rest of the stack via forge-up.sh…"
bash scripts/forge-up.sh 2>&1 | tail -6

# ─── 3. Verify coder role now routes cleanly ─────────────────────

echo
echo "→ Verifying coder role via POST /api/runs (ap-1)…"
WS_ID="$(curl -s http://127.0.0.1:8081/api/workspaces | python3 -c "
import json, sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else (d.get('workspaces') or d.get('data') or [])
print((items or [{}])[0].get('id', ''))
")"
echo "   workspace id: $WS_ID"

body='{"title":"coder-verify","agentPresetId":"ap-1","workspaceId":"'"$WS_ID"'","taskPrompt":"echo hello"}'
resp="$(curl -sS --max-time 20 -X POST -H 'content-type: application/json' -d "$body" http://127.0.0.1:8081/api/runs)"

echo "→ /api/runs response:"
echo "$resp" | python3 -m json.tool 2>/dev/null | head -30 || echo "$resp"

status="$(echo "$resp" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(((d.get('data') or {}).get('status')) or '')
except Exception:
    print('')
")"

if [[ "$status" == "blocked" ]]; then
  err="$(echo "$resp" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(((d.get('data') or {}).get('routing') or {}).get('error') or '')
")"
  echo
  echo "✗ Coder role still blocked. Router error:"
  echo "  $err"
  exit 1
fi

echo
echo "✓ Coder role is live. Run id: $(echo "$resp" | python3 -c "import json,sys; print((json.load(sys.stdin).get('data') or {}).get('id',''))")"

# ─── 4. Best-effort delete of the verification run ────────────────
run_id="$(echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('data') or {}).get('id',''))" 2>/dev/null || true)"
if [[ -n "$run_id" ]]; then
  del_code=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "http://127.0.0.1:8081/api/runs/$run_id" || echo curl_err)
  echo "→ Cleanup: DELETE /api/runs/$run_id → $del_code"
fi

echo "→ Done."
