#!/usr/bin/env bash
# Persist the vLLM coder URL + model overrides to .env so forge-up.sh's
# BFF restart cycle preserves them.  Uses load_dotenv(override=False)
# semantics in bff/services/model_router.py:61.

set -uo pipefail

ENV_FILE="$HOME/dev/forge-oh/.env"

# Discover actual served-model-name from /v1/models (no assumption).
served_name="$(curl -sf --max-time 3 http://localhost:8000/v1/models 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print((d.get('data') or [{}])[0].get('id',''))
except Exception:
    print('')
")"

if [[ -z "$served_name" ]]; then
  echo "✗ Could not reach vLLM on :8000. Aborting." >&2
  exit 1
fi
echo "→ Detected served-model-name on :8000: $served_name"

# 1. Show current .env content for context.
echo
echo "=== current $ENV_FILE ==="
if [[ -f "$ENV_FILE" ]]; then
  cat "$ENV_FILE"
else
  echo "(missing — will be created)"
fi
echo "=== end ==="
echo

# 2. Back up existing .env.
if [[ -f "$ENV_FILE" ]]; then
  cp -a "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
  echo "→ Backed up existing .env"
fi

# 3. Idempotent upsert of the two keys.
python3 - <<PY
from pathlib import Path
p = Path("$ENV_FILE")
lines = p.read_text().splitlines() if p.exists() else []

targets = {
    "LLM_CODER_URL": "http://localhost:8000",
    "LLM_CODER_MODEL": "$served_name",
}

def upsert(existing, key, value):
    new_line = f"{key}={value}"
    for i, line in enumerate(existing):
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
            existing[i] = new_line
            return existing, True
    existing.append(new_line)
    return existing, False

changed = False
for k, v in targets.items():
    lines, updated_existing = upsert(lines, k, v)
    if updated_existing:
        print(f"  ↳ replaced existing {k}")
    else:
        print(f"  ↳ appended {k}")
    changed = True

# Add a header comment if the file was empty.
if not any(l.startswith("# LLM_CODER") or l.startswith("LLM_CODER") for l in lines[:2]):
    pass

p.write_text("\n".join(lines) + "\n")
print(f"→ Wrote {p} ({len(lines)} lines)")
PY

echo
echo "=== new $ENV_FILE ==="
cat "$ENV_FILE"
echo "=== end ==="

# 4. Restart BFF via forge-restart.sh so it re-reads .env at import time.
cd "$HOME/dev/forge-oh"
echo
echo "→ Restarting BFF via forge-restart.sh --bff-only …"
bash scripts/forge-restart.sh --bff-only 2>&1 | tail -8

# 5. Wait for BFF ready, then verify.
for i in $(seq 1 30); do
  curl -sf --max-time 1 http://127.0.0.1:8081/api/agent-presets >/dev/null 2>&1 && break
  sleep 1
done

echo
echo "→ Verifying LLM_CODER_URL / LLM_CODER_MODEL are visible to the new BFF process:"
NEW_PID="$(pgrep -f 'uvicorn.*bff\.main' | head -1)"
if [[ -n "$NEW_PID" ]]; then
  tr '\0' '\n' < "/proc/$NEW_PID/environ" | grep -E "^LLM_CODER_" | sort || echo "  (not set in env — dotenv should still work at import time)"
fi

# 6. Verify coder role via a real /api/runs POST.
echo
echo "→ Verifying coder role via POST /api/runs (ap-1)…"
WS_ID="$(curl -s http://127.0.0.1:8081/api/workspaces | python3 -c "
import json, sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else (d.get('workspaces') or d.get('data') or [])
print((items or [{}])[0].get('id',''))
")"
body='{"title":"coder-verify","agentPresetId":"ap-1","workspaceId":"'"$WS_ID"'","taskPrompt":"echo hello"}'
resp="$(curl -sS --max-time 20 -X POST -H 'content-type: application/json' -d "$body" http://127.0.0.1:8081/api/runs)"
echo "$resp" | python3 -m json.tool 2>/dev/null | head -25 || echo "$resp"

status="$(echo "$resp" | python3 -c "
import json, sys
try: print(((json.load(sys.stdin).get('data') or {}).get('status')) or '')
except Exception: print('')
")"
if [[ "$status" == "blocked" ]]; then
  echo
  echo "✗ Still blocked."
  echo "$resp" | python3 -c "import json, sys; d=json.load(sys.stdin); print('   routing.error:', ((d.get('data') or {}).get('routing') or {}).get('error',''))"
  exit 1
fi

echo
echo "✓ Coder role is live. status=$status"

run_id="$(echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('data') or {}).get('id',''))" 2>/dev/null || true)"
if [[ -n "$run_id" ]]; then
  del_code=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "http://127.0.0.1:8081/api/runs/$run_id" || echo curl_err)
  echo "→ Cleanup: DELETE /api/runs/$run_id → $del_code"
fi

echo "→ Done."
