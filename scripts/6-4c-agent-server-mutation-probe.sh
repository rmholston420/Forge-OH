#!/usr/bin/env bash
# 6-4c-agent-server-mutation-probe.sh
#
# Determine whether agent-server 1.40.0 exposes any endpoint that lets
# us change a conversation's `workspace.working_dir` after creation.
#
# ADR-025 restore-via-fork depends on this because agent-server's fork
# endpoint clones the parent conversation's workspace field verbatim
# (see 6-4c-fork-worktree-probe.sh, VERDICT=inherited).
#
# Read-only side effects: creates a probe run, tries mutations against
# it, deletes it.

set -uo pipefail

BFF="http://127.0.0.1:8081"
AS="http://127.0.0.1:8090"

fail() { echo "✗ $*" >&2; exit 1; }

echo "=== 1. Discover OpenAPI spec from agent-server ==="
spec="$(curl -sf "$AS/openapi.json" 2>/dev/null || curl -sf "$AS/api/openapi.json" 2>/dev/null || echo '')"
if [[ -z "$spec" ]]; then
  echo "  ! /openapi.json not exposed by agent-server."
else
  echo "  ✓ OpenAPI spec fetched ($(echo "$spec" | wc -c) bytes)"
  echo
  echo "  --- Endpoints that touch conversations or workspaces ---"
  echo "$spec" | python3 -c "
import json, sys
spec = json.load(sys.stdin)
paths = spec.get('paths', {})
for p, methods in sorted(paths.items()):
    if 'conversation' in p.lower() or 'workspace' in p.lower():
        for m in methods:
            if m.upper() in ('GET','POST','PUT','PATCH','DELETE'):
                print(f'    {m.upper():6s} {p}')
"
fi

echo
echo "=== 2. Create a probe run ==="
WS_JSON="$(curl -sf "$BFF/api/workspaces" 2>/dev/null)"
WS_ID="$(echo "$WS_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
items = d if isinstance(d, list) else (d.get('workspaces') or d.get('data') or [])
print((items or [{}])[0].get('id',''))
")"
[[ -z "$WS_ID" ]] && fail "No workspaces"

create_body="$(python3 -c "
import json
print(json.dumps({
    'title': '6.4c-mutation-probe',
    'agentPresetId': 'ap-1',
    'workspaceId': '$WS_ID',
    'taskPrompt': 'echo probe',
}))")"
resp="$(curl -sS --max-time 20 -X POST -H 'content-type: application/json' \
  -d "$create_body" "$BFF/api/runs")"
RUN_ID="$(echo "$resp" | python3 -c "
import json, sys
try: print((json.load(sys.stdin).get('data') or {}).get('id',''))
except Exception: print('')
")"
[[ -z "$RUN_ID" ]] && { echo "$resp" | head -20; fail "create failed"; }
echo "  probe run_id: $RUN_ID"

# 2.5 Get the current working_dir
sleep 1
conv="$(curl -sf "$AS/api/conversations/$RUN_ID" 2>/dev/null)"
CURRENT_WD="$(echo "$conv" | python3 -c "
import json, sys
try: print(((json.load(sys.stdin).get('workspace') or {}).get('working_dir')) or '')
except Exception: print('')
")"
echo "  current working_dir: $CURRENT_WD"

# Target a path that DOES NOT exist so a successful mutation without
# actual filesystem work is visible in the returned working_dir.
TARGET_WD="/tmp/6-4c-mutation-probe-target-$$"

echo
echo "=== 3. Try PATCH /api/conversations/{id} with new working_dir ==="
patch_code=$(curl -sS -o /tmp/probe-patch.json -w '%{http_code}' \
  -X PATCH -H 'content-type: application/json' \
  -d "{\"workspace\":{\"working_dir\":\"$TARGET_WD\",\"kind\":\"LocalWorkspace\"}}" \
  "$AS/api/conversations/$RUN_ID" 2>/dev/null || echo err)
echo "  PATCH http_code: $patch_code"
echo "  PATCH response:  $(head -c 300 /tmp/probe-patch.json 2>/dev/null)"

echo
echo "=== 4. Try PUT /api/conversations/{id} with new working_dir ==="
put_code=$(curl -sS -o /tmp/probe-put.json -w '%{http_code}' \
  -X PUT -H 'content-type: application/json' \
  -d "{\"workspace\":{\"working_dir\":\"$TARGET_WD\",\"kind\":\"LocalWorkspace\"}}" \
  "$AS/api/conversations/$RUN_ID" 2>/dev/null || echo err)
echo "  PUT http_code: $put_code"
echo "  PUT response:  $(head -c 300 /tmp/probe-put.json 2>/dev/null)"

echo
echo "=== 5. Try PATCH nested: /api/conversations/{id}/workspace ==="
sub_patch_code=$(curl -sS -o /tmp/probe-sub-patch.json -w '%{http_code}' \
  -X PATCH -H 'content-type: application/json' \
  -d "{\"working_dir\":\"$TARGET_WD\",\"kind\":\"LocalWorkspace\"}" \
  "$AS/api/conversations/$RUN_ID/workspace" 2>/dev/null || echo err)
echo "  PATCH /workspace http_code: $sub_patch_code"
echo "  PATCH /workspace response:  $(head -c 300 /tmp/probe-sub-patch.json 2>/dev/null)"

echo
echo "=== 6. Verify working_dir after mutation attempts ==="
sleep 1
after="$(curl -sf "$AS/api/conversations/$RUN_ID" 2>/dev/null)"
AFTER_WD="$(echo "$after" | python3 -c "
import json, sys
try: print(((json.load(sys.stdin).get('workspace') or {}).get('working_dir')) or '')
except Exception: print('')
")"
echo "  post-mutation working_dir: $AFTER_WD"
if [[ "$AFTER_WD" == "$TARGET_WD" ]]; then
  echo "  ✓ Mutation SUCCEEDED — working_dir was updated"
elif [[ "$AFTER_WD" == "$CURRENT_WD" ]]; then
  echo "  ✗ Mutation had no effect — working_dir unchanged"
else
  echo "  ⚠ Unexpected state — working_dir changed to something unexpected"
fi

echo
echo "=== 7. Verdict ==="
if [[ "$patch_code" == "200" || "$patch_code" == "202" || "$patch_code" == "204" \
   || "$put_code"   == "200" || "$put_code"   == "202" || "$put_code"   == "204" \
   || "$sub_patch_code" == "200" || "$sub_patch_code" == "202" || "$sub_patch_code" == "204" ]] \
   && [[ "$AFTER_WD" == "$TARGET_WD" ]]; then
  echo "VERDICT = mutable"
  echo
  echo "✓ ADR-025 amendment path: after fork, mutate the fork's working_dir"
  echo "  to a freshly provisioned worktree before running git reset."
else
  echo "VERDICT = immutable"
  echo
  echo "⚠  No usable working_dir mutation endpoint.  ADR-025 must be"
  echo "   superseded by a new design (see ADR-026 candidate options)."
fi

echo
echo "=== 8. Cleanup ==="
del=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "$BFF/api/runs/$RUN_ID" || echo err)
echo "  DELETE probe run: $del"
rm -f /tmp/probe-patch.json /tmp/probe-put.json /tmp/probe-sub-patch.json
