#!/usr/bin/env bash
# forge-doctor.sh — one-shot Forge-OH health diagnostic
#
# Prints everything I would want to see before answering "why isn't X
# working". Paste the output verbatim into a chat and I can diagnose
# without a round-trip.
#
# Sections (in order):
#   1. Environment: git branch/status/HEAD, .oh-venv sanity
#   2. Process/port health (delegates to forge-status.sh)
#   3. Service probes: each expected HTTP endpoint (BFF, agent-server,
#      vLLM coder, vLLM planner, Ollama). Times each one.
#   4. Workspace UUIDs currently registered by the BFF
#   5. Agent presets exposed by the BFF (with default-id highlighted)
#   6. Selfeval unit state + last cycle summary (if any)
#   7. Recent BFF errors (last 40 lines)
#   8. Recent agent-server errors (last 20 lines)
#   9. Recent Next.js errors (last 20 lines)
#
# Read-only — never mutates anything. Safe to run at any time.
#
# Usage:
#   bash scripts/forge-doctor.sh
#   bash scripts/forge-doctor.sh --json   # machine-readable (subset)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

JSON_MODE=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON_MODE=1 ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's|^#\{1,\} \{0,1\}||'
      exit 0
      ;;
  esac
done

LOG_DIR="$REPO_ROOT/.forge-logs"
BFF_PORT="${BFF_PORT:-8081}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"
VLLM_CODER_PORT="${VLLM_CODER_PORT:-8501}"
VLLM_PLANNER_PORT="${VLLM_PLANNER_PORT:-8511}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

BFF="http://127.0.0.1:${BFF_PORT}"
AGENT="http://127.0.0.1:${AGENT_PORT}"
CODER="http://127.0.0.1:${VLLM_CODER_PORT}"
PLANNER="http://127.0.0.1:${VLLM_PLANNER_PORT}"
OLLAMA="http://127.0.0.1:${OLLAMA_PORT}"

hdr() { printf '\n\033[36m═══ %s ═══\033[0m\n' "$*"; }
sub() { printf '\033[35m› %s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad() { printf '  \033[31m✗\033[0m %s\n' "$*"; }
inf() { printf '  \033[33m·\033[0m %s\n' "$*"; }

# ---- 1. Environment ------------------------------------------------------
hdr "1. Environment"
sub "git"
inf "branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
inf "HEAD:   $(git log -1 --oneline 2>/dev/null || echo '?')"
DIRTY="$(git status --porcelain 2>/dev/null | wc -l)"
if [ "$DIRTY" -eq 0 ]; then
  ok "working tree clean"
else
  bad "$DIRTY file(s) modified/untracked"
  git status --short 2>/dev/null | sed 's|^|      |' | head -20
fi
UPSTREAM="$(git rev-parse --abbrev-ref '@{u}' 2>/dev/null || true)"
if [ -n "$UPSTREAM" ]; then
  AHEAD="$(git rev-list --count "$UPSTREAM"..HEAD 2>/dev/null || echo 0)"
  BEHIND="$(git rev-list --count HEAD.."$UPSTREAM" 2>/dev/null || echo 0)"
  inf "vs $UPSTREAM: ahead=$AHEAD behind=$BEHIND"
fi

sub ".oh-venv"
if [ -x .oh-venv/bin/python ]; then
  ok "$(.oh-venv/bin/python --version 2>&1) at .oh-venv/bin/python"
  PY_VER="$(.oh-venv/bin/python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo '?')"
  inf "openhands: $(.oh-venv/bin/python -c 'import openhands; print(openhands.__version__ if hasattr(openhands, "__version__") else "installed (no __version__)")' 2>&1 | head -1)"
  inf "openhands_tools_ext: $(.oh-venv/bin/python -c 'import openhands_tools_ext; print("importable")' 2>&1 | head -1)"
  inf "selfeval CLI: $(.oh-venv/bin/python -c 'from openhands_tools_ext.selfeval.cli import main; print("importable")' 2>&1 | head -1)"
else
  bad ".oh-venv/bin/python missing"
fi

# ---- 2. Process/port health ---------------------------------------------
hdr "2. Process/port health"
if [ -x scripts/forge-status.sh ]; then
  bash scripts/forge-status.sh 2>&1 | sed 's|^|  |'
else
  bad "scripts/forge-status.sh not executable"
fi

# ---- 3. Service probes ---------------------------------------------------
hdr "3. HTTP probes"
probe() {
  local name="$1" url="$2" expect_json="${3:-0}"
  local t0 t1 dt code body
  t0="$(date +%s%N)"
  # -m 5 = 5s connect+read cap. --fail-with-body returns 22 on 4xx/5xx but
  # still prints. We ignore exit and inspect http_code separately.
  body="$(curl -sS -m 5 -o /tmp/forge-doctor-body.$$ -w '%{http_code}' "$url" 2>&1 || true)"
  t1="$(date +%s%N)"
  dt=$(( (t1 - t0) / 1000000 ))
  code="$body"
  if [ "$code" = "000" ] || ! [[ "$code" =~ ^[0-9]+$ ]]; then
    bad "$(printf '%-24s %s → %s (%dms)' "$name" "$url" "unreachable" "$dt")"
    return 1
  fi
  if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then
    ok "$(printf '%-24s %s → HTTP %s (%dms)' "$name" "$url" "$code" "$dt")"
  else
    bad "$(printf '%-24s %s → HTTP %s (%dms)' "$name" "$url" "$code" "$dt")"
  fi
  if [ "$expect_json" = "1" ] && [ -s /tmp/forge-doctor-body.$$ ]; then
    head -c 200 /tmp/forge-doctor-body.$$ | sed 's|^|      |'
    printf '\n'
  fi
  rm -f /tmp/forge-doctor-body.$$
}
probe "BFF /docs"           "$BFF/docs"
probe "BFF /api/workspaces" "$BFF/api/workspaces" 0
probe "BFF /api/agent-presets" "$BFF/api/agent-presets" 0
probe "agent-server /docs"  "$AGENT/docs"
probe "vLLM coder /health"  "$CODER/health"
probe "vLLM planner /health" "$PLANNER/health"
probe "Ollama /"            "$OLLAMA/"

# ---- 4. Workspaces -------------------------------------------------------
hdr "4. Workspaces"
if command -v jq >/dev/null 2>&1; then
  WS_JSON="$(curl -sS -m 3 "$BFF/api/workspaces" 2>/dev/null || true)"
  if [ -n "$WS_JSON" ]; then
    echo "$WS_JSON" | jq -r '.data[]? | "  · \(.name)  id=\(.id)  path=\(.path // "?")"' 2>/dev/null \
      || inf "response not JSON: $(printf '%s' "$WS_JSON" | head -c 120)"
  else
    bad "no response from BFF"
  fi
else
  inf "install jq for pretty workspace listing"
  curl -sS -m 3 "$BFF/api/workspaces" 2>/dev/null | head -c 400
  echo
fi

# ---- 5. Agent presets ----------------------------------------------------
hdr "5. Agent presets"
if command -v jq >/dev/null 2>&1; then
  AP_JSON="$(curl -sS -m 3 "$BFF/api/agent-presets" 2>/dev/null || true)"
  if [ -n "$AP_JSON" ]; then
    echo "$AP_JSON" | jq -r '.data[]? | "  · \(.name)  id=\(.id)  default=\(.isDefault)  model=\(.model)"' 2>/dev/null \
      || inf "response not JSON: $(printf '%s' "$AP_JSON" | head -c 120)"
    DEFAULT_ID="$(echo "$AP_JSON" | jq -r '.data[]? | select(.isDefault==true) | .id' 2>/dev/null | head -n1)"
    if [ -n "$DEFAULT_ID" ]; then
      ok "default agentPresetId: $DEFAULT_ID"
    else
      bad "no preset flagged isDefault=true"
    fi
  else
    bad "no response from BFF"
  fi
else
  curl -sS -m 3 "$BFF/api/agent-presets" 2>/dev/null | head -c 400
  echo
fi

# ---- 6. Selfeval unit + last cycle --------------------------------------
hdr "6. Self-eval unit + last cycle"
UNIT_STATE="$(systemctl --user is-active forge-oh-selfeval.service 2>/dev/null || echo 'unknown')"
UNIT_RESULT="$(systemctl --user show -p Result --value forge-oh-selfeval.service 2>/dev/null || echo '?')"
inf "unit is-active: $UNIT_STATE"
inf "unit Result:    $UNIT_RESULT"

LATEST_SUMMARY="$(ls -1t docs/selfeval/*-selfeval.json 2>/dev/null | head -n1 || true)"
if [ -n "$LATEST_SUMMARY" ]; then
  inf "latest summary: $LATEST_SUMMARY"
  if command -v jq >/dev/null 2>&1; then
    jq -r '"  passed=\(.tasks_passed) failed=\(.tasks_failed) timeout=\(.tasks_timed_out) error=\(.tasks_errored // .tasks_error // 0) selected=\(.tasks_selected)"' \
      "$LATEST_SUMMARY" 2>/dev/null | sed 's|^|  |'
    jq -r '.outcomes[]? | "  · \(.task_id): \(.verdict) (\(.duration_sec|floor)s) \(.failure_detail // "")"' \
      "$LATEST_SUMMARY" 2>/dev/null | sed 's|^|  |' | head -10
  else
    head -c 400 "$LATEST_SUMMARY"
    echo
  fi
else
  inf "no summary yet in docs/selfeval/"
fi

LATEST_PROPOSALS="$(ls -1t docs/proposals/*.md 2>/dev/null | head -n 5 || true)"
if [ -n "$LATEST_PROPOSALS" ]; then
  sub "recent proposals (top 5)"
  echo "$LATEST_PROPOSALS" | sed 's|^|  · |'
fi

# ---- 7. Recent BFF errors ------------------------------------------------
hdr "7. Recent BFF log (POST /api/runs history + errors + tail)"
if [ -f "$LOG_DIR/bff.log" ]; then
  # Segment the log tail so GPU polls don't drown the signal.
  sub "POST /api/runs history (last 20)"
  grep -nE 'POST /api/runs' "$LOG_DIR/bff.log" | tail -n 20 | sed 's|^|  |'
  sub "errors/exceptions (last 20 from last 400 lines)"
  tail -n 400 "$LOG_DIR/bff.log" | grep -iE 'error|exception|traceback|500|422|warning' | tail -n 20 | sed 's|^|  |'
  sub "raw tail (last 20)"
  tail -n 20 "$LOG_DIR/bff.log" | sed 's|^|  |'
else
  bad "no $LOG_DIR/bff.log"
fi

# ---- 8. Recent agent-server errors --------------------------------------
hdr "8. Recent agent-server log (POST /api/conversations history + errors + tail)"
if [ -f "$LOG_DIR/agent-server.log" ]; then
  sub "POST /api/conversations (last 10)"
  grep -nE 'POST /api/conversations' "$LOG_DIR/agent-server.log" | tail -n 10 | sed 's|^|  |'
  sub "errors/exceptions (last 10 from last 400 lines)"
  tail -n 400 "$LOG_DIR/agent-server.log" | grep -iE 'ERROR|Exception|Traceback|500|502|503' | tail -n 10 | sed 's|^|  |'
  sub "raw tail (last 20)"
  tail -n 20 "$LOG_DIR/agent-server.log" | sed 's|^|  |'
else
  bad "no $LOG_DIR/agent-server.log"
fi

# ---- 9. Recent Next.js log ----------------------------------------------
hdr "9. Recent Next.js log (last 20 lines)"
if [ -f "$LOG_DIR/frontend.log" ]; then
  tail -n 20 "$LOG_DIR/frontend.log" | sed 's|^|  |'
else
  bad "no $LOG_DIR/frontend.log"
fi

# ---- 10. Colossus <-> GitHub mirror parity (ADR-016) --------------------
hdr "10. Colossus <-> GitHub mirror parity (ADR-016)"
DRIFT="$(git ls-files --others --exclude-standard 2>/dev/null || true)"
if [ -z "$DRIFT" ]; then
  echo "  OK  no drift - every file is tracked or explicitly ignored"
else
  DRIFT_COUNT=$(echo "$DRIFT" | wc -l)
  bad "DRIFT: $DRIFT_COUNT file(s) exist on Colossus but are neither tracked nor ignored:"
  echo "$DRIFT" | sed 's|^|    |'
  echo ""
  echo "  Per ADR-016, each must be: tracked (git add), ignored (.gitignore + rationale), or deleted."
fi

# Unpushed commits check.
UPSTREAM=$(git rev-parse --abbrev-ref '@{u}' 2>/dev/null || echo "")
if [ -n "$UPSTREAM" ]; then
  AHEAD=$(git rev-list --count "$UPSTREAM"..HEAD 2>/dev/null || echo "?")
  if [ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ]; then
    bad "UNPUSHED: local branch is $AHEAD commit(s) ahead of $UPSTREAM."
    echo "  Per ADR-016 (every commit pushes same turn): git push"
  fi
fi

hdr "Done"
