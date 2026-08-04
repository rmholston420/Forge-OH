#!/bin/bash
# F.19.4 Phase 2 — full BFF /api/runs round-trip smoke.
#
# Requires:
#   - BFF running at :8081 (bff/main.py)
#   - OpenHands agent-server running at :8090
#   - Coder or planner vLLM live (supervisor will swap on demand)
#
# Sends the 3 canonical prompts via POST /api/runs with the right
# taskComplexity and asserts the response.routing.role matches.
#
# NOTE: no `set -euo pipefail` per user preference.

BFF_URL="${BFF_URL:-http://127.0.0.1:8081}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROMPTS_DIR="$REPO_ROOT/bench/prompts"

# BFF /api/workspaces returns list[Workspace] directly. Pick the first;
# fall back to "default" if none registered (agent-server maps default
# -> workspace/runs/pending; fine for smoke but not real agent execution).
WS_ID="$(curl -sS --max-time 10 "$BFF_URL/api/workspaces" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    ws = d if isinstance(d, list) else (d.get("workspaces") or [])
    if ws:
        print(ws[0]["id"])
except Exception:
    pass
')"
if [ -z "$WS_ID" ]; then
    echo "no workspace found on agent-server; falling back to 'default'" >&2
    WS_ID="default"
fi
echo "[smoke] workspace_id=$WS_ID"

run_one() {
    local name="$1"; local tc="$2"; local prompt_file="$3"; local expect_role="$4"
    local prompt
    prompt="$(cat "$prompt_file")"
    echo
    echo "=== $name ($tc → expect role=$expect_role) ==="

    local payload
    payload="$(python3 -c '
import json, sys
prompt = sys.stdin.read()
print(json.dumps({
    "title": "F.19.4 smoke '"$name"'",
    "taskPrompt": prompt,
    "taskComplexity": "'"$tc"'",
    "workspaceId": "'"$WS_ID"'",
    "agentPresetId": "default",
}))
' <<< "$prompt")"

    local resp
    local t0=$(date +%s)
    # 20-minute timeout: allows one supervisor swap (~8 min with slop) + generation.
    resp="$(curl -sS --max-time 1200 -X POST "$BFF_URL/api/runs" \
        -H 'Content-Type: application/json' \
        --data "$payload")"
    local rc=$?
    local elapsed=$(( $(date +%s) - t0 ))
    echo "[smoke] $name curl rc=$rc elapsed=${elapsed}s"
    echo "response:"
    echo "$resp" | python3 -m json.tool 2>/dev/null | head -30 || echo "$resp"

    # Assert routing.role
    local got_role
    got_role="$(echo "$resp" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print((d.get("data") or {}).get("routing", {}).get("role", ""))
except Exception:
    print("")
')"
    if [ "$got_role" = "$expect_role" ]; then
        echo "[smoke] $name PASS (role=$got_role)"
    else
        echo "[smoke] $name FAIL (expected role=$expect_role, got role='$got_role')"
    fi
}

run_one "P1" "simple"   "$PROMPTS_DIR/arch.txt"  "coder"
run_one "P2" "medium"   "$PROMPTS_DIR/debug.txt" "coder"
run_one "P3" "planning" "$PROMPTS_DIR/plan.txt"  "planner"

echo
echo "=== F.19.4 Phase 2 done ==="
