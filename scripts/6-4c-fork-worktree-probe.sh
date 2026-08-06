#!/usr/bin/env bash
# 6-4c-fork-worktree-probe.sh — Determine whether agent-server's fork
# endpoint gives the child conversation a fresh working_dir or clones
# the parent's.
#
# Read-only side effects: creates a run + forks it, then deletes both.
#
# Output surface:
#   PARENT working_dir  = <path>
#   FORK   working_dir  = <path>
#   VERDICT             = fresh | inherited | unknown
#
# ADR-025 Stage 6.4c depends on this outcome.  Do not implement restore
# until this returns 'fresh' or the ADR is amended.

set -uo pipefail

BFF="http://127.0.0.1:8081"

fail() { echo "✗ $*" >&2; exit 1; }

echo "=== 1. Pick a workspace ==="
WS_JSON="$(curl -sf "$BFF/api/workspaces" 2>/dev/null || echo '')"
[[ -z "$WS_JSON" ]] && fail "BFF /api/workspaces unreachable"
WS_ID="$(echo "$WS_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else (d.get('workspaces') or d.get('data') or [])
print((items or [{}])[0].get('id',''))
")"
[[ -z "$WS_ID" ]] && fail "No workspaces returned"
echo "  workspaceId: $WS_ID"

echo
echo "=== 2. Pick default agent preset (ap-1) ==="
PRESET_ID="ap-1"
echo "  agentPresetId: $PRESET_ID"

echo
echo "=== 3. Create parent run ==="
create_body="$(python3 -c "
import json
print(json.dumps({
    'title': '6.4c-probe-parent',
    'agentPresetId': '$PRESET_ID',
    'workspaceId': '$WS_ID',
    'taskPrompt': 'echo probe',
}))")"

parent_resp="$(curl -sS --max-time 20 -X POST \
  -H 'content-type: application/json' \
  -d "$create_body" \
  "$BFF/api/runs")"
PARENT_ID="$(echo "$parent_resp" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print((d.get('data') or {}).get('id',''))
except Exception:
    print('')
")"
[[ -z "$PARENT_ID" ]] && { echo "$parent_resp" | head -20; fail "parent create failed"; }
echo "  parent run_id: $PARENT_ID"

# 3.5 Grab parent working_dir from agent-server (BFF proxy)
sleep 1
parent_conv="$(curl -sf "$BFF/api/agent/conversations/$PARENT_ID" 2>/dev/null || echo '')"
if [[ -z "$parent_conv" ]]; then
  # Try the direct agent-server port
  parent_conv="$(curl -sf "http://127.0.0.1:8090/api/conversations/$PARENT_ID" 2>/dev/null || echo '')"
fi
PARENT_WD="$(echo "$parent_conv" | python3 -c "
import json, sys
try:
    print(((json.load(sys.stdin).get('workspace') or {}).get('working_dir')) or '')
except Exception:
    print('')
")"
echo "  parent working_dir: $PARENT_WD"

echo
echo "=== 4. Fork parent (no from_event_id) ==="
fork_resp="$(curl -sS --max-time 20 -X POST \
  -H 'content-type: application/json' \
  -d '{}' \
  "$BFF/api/runs/$PARENT_ID/fork")"
echo "$fork_resp" | python3 -m json.tool 2>/dev/null | head -10 || echo "$fork_resp"
FORK_ID="$(echo "$fork_resp" | python3 -c "
import json, sys
try:
    print(json.load(sys.stdin).get('forked_id',''))
except Exception:
    print('')
")"
[[ -z "$FORK_ID" ]] && { echo "$fork_resp" | head -30; fail "fork failed"; }
echo "  fork run_id: $FORK_ID"

echo
echo "=== 5. Inspect fork's working_dir ==="
sleep 1
fork_conv="$(curl -sf "http://127.0.0.1:8090/api/conversations/$FORK_ID" 2>/dev/null || echo '')"
FORK_WD="$(echo "$fork_conv" | python3 -c "
import json, sys
try:
    print(((json.load(sys.stdin).get('workspace') or {}).get('working_dir')) or '')
except Exception:
    print('')
")"
echo "  fork working_dir:   $FORK_WD"

echo
echo "=== 6. Verdict ==="
echo "PARENT working_dir = $PARENT_WD"
echo "FORK   working_dir = $FORK_WD"
if [[ -z "$PARENT_WD" || -z "$FORK_WD" ]]; then
  echo "VERDICT = unknown (one of the paths came back empty)"
elif [[ "$PARENT_WD" == "$FORK_WD" ]]; then
  echo "VERDICT = inherited"
  echo
  echo "⚠️  ADR-025 needs amendment: fork inherits parent's worktree,"
  echo "    so 'reset --hard in the fork's worktree' would destroy parent"
  echo "    files.  Restore must provision a fresh worktree post-fork and"
  echo "    the fork's working_dir must be rewritten to it."
else
  echo "VERDICT = fresh"
  echo
  echo "✓ ADR-025 as written is sound: fork already has its own worktree."
fi

echo
echo "=== 7. Extra evidence: filesystem check ==="
if [[ -n "$PARENT_WD" ]]; then
  echo "parent path exists: $([[ -d $PARENT_WD ]] && echo yes || echo no)"
  echo "parent .git head:   $(cat "$PARENT_WD/.git/HEAD" 2>/dev/null || echo 'n/a')"
fi
if [[ -n "$FORK_WD" ]]; then
  echo "fork path exists:   $([[ -d $FORK_WD ]] && echo yes || echo no)"
  echo "fork .git head:     $(cat "$FORK_WD/.git/HEAD" 2>/dev/null || echo 'n/a')"
fi

echo
echo "=== 8. Cleanup ==="
del1=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "$BFF/api/runs/$FORK_ID" || echo err)
del2=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "$BFF/api/runs/$PARENT_ID" || echo err)
echo "  DELETE fork:   $del1"
echo "  DELETE parent: $del2"
