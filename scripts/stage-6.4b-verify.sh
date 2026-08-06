#!/usr/bin/env bash
# Stage 6.4b DoD verification (ADR-025).
#
# DoD (from ADR-025 §Decision · Stage 6.4b):
#   Two concurrent runs against the same workspace do not observe each
#   other's file changes; `git worktree list` shows both; run_compare
#   still works between them.
#
# This script is NON-DESTRUCTIVE and does not depend on the LLM finishing
# any actual work.  It fires two POST /runs against the same workspace,
# then immediately probes the filesystem + agent-server state.  Runs are
# cancelled cleanly at the end via DELETE /runs/{id}.
#
# Prereqs: BFF on :8081, agent-server on :8090, at least one workspace
# registered whose ``path`` is a real git repo.
#
# Usage:
#   scripts/stage-6.4b-verify.sh              # auto-picks first git workspace
#   scripts/stage-6.4b-verify.sh <workspace-id>

set -euo pipefail

BFF="${BFF_URL:-http://127.0.0.1:8081}"
WORKTREE_ROOT="${FORGE_WORKTREE_ROOT:-$HOME/.forge-oh/worktrees}"

# ─── 1. Pick workspace ──────────────────────────────────────────────

# Small helper to normalise the workspaces payload into a JSON list.
# Handles all three shapes seen in agent-server / BFF releases:
#   * bare list            e.g. [{...}, {...}]
#   * {"workspaces":[...]}
#   * {"data":[...]} / {"items":[...]}
_read_workspaces() {
  python3 -c "
import json, sys
data = json.load(sys.stdin)
if isinstance(data, list):
    items = data
elif isinstance(data, dict):
    items = data.get('workspaces') or data.get('data') or data.get('items') or []
else:
    items = []
print(json.dumps(items))
"
}

if [[ $# -ge 1 ]]; then
  WS_ID="$1"
else
  echo "→ Looking for a workspace whose path is a git repo…"
  workspaces_json="$(curl -s "$BFF/api/workspaces" || true)"
  if [[ -z "$workspaces_json" ]]; then
    echo "✗ Could not fetch workspaces from $BFF/api/workspaces" >&2
    exit 1
  fi

  items_json="$(printf '%s' "$workspaces_json" | _read_workspaces)"
  echo "   payload preview: $(printf '%s' "$items_json" | head -c 240)"

  # Pick the first workspace whose path is a git repo on disk.
  WS_ID="$(printf '%s' "$items_json" | python3 -c "
import json, os, sys
items = json.load(sys.stdin)
for w in items:
    path = (w or {}).get('path') or ''
    if path and os.path.exists(os.path.join(path, '.git')):
        print(w.get('id'))
        sys.exit(0)
sys.exit(1)
")" || {
    echo "✗ No git-backed workspace found; pass an id explicitly." >&2
    exit 1
  }
fi

echo "→ Using workspace id: $WS_ID"

WS_PATH="$(curl -s "$BFF/api/workspaces" | _read_workspaces | python3 -c "
import json, sys
items = json.load(sys.stdin)
for w in items:
    if (w or {}).get('id') == '$WS_ID':
        print(w.get('path', ''))
        break
")"
echo "→ Workspace path: $WS_PATH"

if [[ ! -e "$WS_PATH/.git" ]]; then
  echo "✗ $WS_PATH is not a git repo — worktree provisioning will silently degrade (A1)." >&2
  echo "   Aborting verify so we don't produce a false-positive result." >&2
  exit 1
fi

# ─── 2. Baseline worktree count ────────────────────────────────────

echo "→ Existing worktrees under $WORKTREE_ROOT:"
before_count=0
if [[ -d "$WORKTREE_ROOT" ]]; then
  before_count=$(find "$WORKTREE_ROOT" -maxdepth 1 -mindepth 1 -type d | wc -l)
fi
echo "   count=$before_count"

# ─── 3. Fire two concurrent runs ───────────────────────────────────

echo "→ Firing two concurrent POST /api/runs against workspace $WS_ID…"

mkfifo /tmp/wt-r1 /tmp/wt-r2 2>/dev/null || true
rm -f /tmp/wt-r1 /tmp/wt-r2

# We use --max-time 15 so a hung LLM/agent-server doesn't wedge the
# script; we don't care whether the LLM ever fires — we only need the
# BFF to reach the create_run body far enough to provision the worktree
# and hand back the {run_id, working_dir}.  On a coder role that hasn't
# warmed up, the actual /run kick-off will still be in flight when we
# probe.
body='{"title":"6.4b-verify","agentPresetId":"ap-1","workspaceId":"'"$WS_ID"'","taskPrompt":"noop"}'

curl -sS --max-time 15 -X POST -H 'content-type: application/json' -d "$body" \
     "$BFF/api/runs" > /tmp/wt-r1.json &
p1=$!
curl -sS --max-time 15 -X POST -H 'content-type: application/json' -d "$body" \
     "$BFF/api/runs" > /tmp/wt-r2.json &
p2=$!
wait $p1 || echo "  (r1 curl exited non-zero — may be a timeout, not fatal)"
wait $p2 || echo "  (r2 curl exited non-zero — may be a timeout, not fatal)"

echo
echo "→ r1 response:"
cat /tmp/wt-r1.json | python3 -m json.tool 2>/dev/null | head -30 || cat /tmp/wt-r1.json
echo
echo "→ r2 response:"
cat /tmp/wt-r2.json | python3 -m json.tool 2>/dev/null | head -30 || cat /tmp/wt-r2.json

run1_id="$(python3 -c "import json; d=json.load(open('/tmp/wt-r1.json')); print((d.get('data') or {}).get('id',''))" 2>/dev/null || true)"
run2_id="$(python3 -c "import json; d=json.load(open('/tmp/wt-r2.json')); print((d.get('data') or {}).get('id',''))" 2>/dev/null || true)"
echo
echo "→ run1_id=$run1_id"
echo "→ run2_id=$run2_id"

# ─── 4. Probe worktree state ───────────────────────────────────────

echo
echo "→ Worktrees under $WORKTREE_ROOT after both creates:"
after_count=0
if [[ -d "$WORKTREE_ROOT" ]]; then
  find "$WORKTREE_ROOT" -maxdepth 1 -mindepth 1 -type d | sort
  after_count=$(find "$WORKTREE_ROOT" -maxdepth 1 -mindepth 1 -type d | wc -l)
fi
echo "   count=$after_count (expected: $((before_count + 2)) if isolation is working)"

echo
echo "→ git worktree list on source repo $WS_PATH:"
git -C "$WS_PATH" worktree list --porcelain | grep -E "^worktree " | sort

# ─── 5. Isolation invariant: write distinct files in each worktree ──

if [[ $after_count -ge $((before_count + 2)) ]]; then
  # Pull the two most recently created worktrees.
  wts=($(find "$WORKTREE_ROOT" -maxdepth 1 -mindepth 1 -type d -printf '%T@ %p\n' | sort -n | tail -2 | awk '{print $2}'))
  wt_a="${wts[0]}"
  wt_b="${wts[1]}"
  echo
  echo "→ Writing marker files in each worktree:"
  echo "   $wt_a  ← unique-to-A.txt"
  echo "   $wt_b  ← unique-to-B.txt"
  echo "A" > "$wt_a/unique-to-A.txt"
  echo "B" > "$wt_b/unique-to-B.txt"

  echo
  echo "→ Isolation checks:"
  if [[ -f "$wt_b/unique-to-A.txt" ]]; then
    echo "   ✗ FAIL: A's file leaked into B"
  else
    echo "   ✓ A's file NOT visible in B"
  fi
  if [[ -f "$wt_a/unique-to-B.txt" ]]; then
    echo "   ✗ FAIL: B's file leaked into A"
  else
    echo "   ✓ B's file NOT visible in A"
  fi
  if [[ -f "$WS_PATH/unique-to-A.txt" || -f "$WS_PATH/unique-to-B.txt" ]]; then
    echo "   ✗ FAIL: marker file leaked into source workspace $WS_PATH"
  else
    echo "   ✓ neither marker leaked into source workspace"
  fi
fi

# ─── 6. Cleanup: DELETE each run to reap worktrees ─────────────────

echo
echo "→ Deleting both runs (this should reap their worktrees):"
for rid in "$run1_id" "$run2_id"; do
  if [[ -n "$rid" ]]; then
    code=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "$BFF/api/runs/$rid" || echo "curl_err")
    echo "   DELETE /api/runs/$rid  → $code"
  fi
done

echo
echo "→ Worktrees under $WORKTREE_ROOT after cleanup:"
find "$WORKTREE_ROOT" -maxdepth 1 -mindepth 1 -type d | sort
final_count=$(find "$WORKTREE_ROOT" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
echo "   count=$final_count (expected: $before_count if cleanup is working)"

echo
echo "→ Done."
