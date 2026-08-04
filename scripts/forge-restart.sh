#!/usr/bin/env bash
# forge-restart.sh — bounce Forge-OH cleanly
#
# Runs forge-down.sh, waits for ports to free, then forge-up.sh.
# Same scope: agent-server (:8090), BFF (:8081), Next.js (:3000).
# vLLM containers are NEVER touched here — they warm up too slowly to
# bounce casually and the supervisor manages them independently.
#
# Flags:
#   --frontend    Also bounce Next.js. Default (no flag) still restarts
#                 it because forge-down kills it and forge-up starts it,
#                 but this flag is preserved for future partial-restart
#                 modes. Currently a no-op sentinel.
#   --bff-only    Restart only the BFF (leave agent-server + Next.js
#                 alone). Useful when only BFF Python code changed and
#                 --reload didn't pick it up (e.g. new router).
#   --status      After restart, print `forge-status.sh` output.
#
# Usage:
#   bash scripts/forge-restart.sh
#   bash scripts/forge-restart.sh --bff-only
#   bash scripts/forge-restart.sh --status
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FRONTEND=0
BFF_ONLY=0
SHOW_STATUS=0
for arg in "$@"; do
  case "$arg" in
    --frontend) FRONTEND=1 ;;
    --bff-only) BFF_ONLY=1 ;;
    --status)   SHOW_STATUS=1 ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's|^#\{1,\} \{0,1\}||'
      exit 0
      ;;
    *)
      printf '[forge-restart] unknown flag: %s\n' "$arg" >&2
      exit 2
      ;;
  esac
done

log() { printf '\033[36m[forge-restart]\033[0m %s\n' "$*"; }

BFF_PORT="${BFF_PORT:-8081}"
LOG_DIR="$REPO_ROOT/.forge-logs"

if [ "$BFF_ONLY" -eq 1 ]; then
  # Partial: down + up the BFF only. Reuses the same pid-file and port
  # discipline as forge-up.sh so nothing goes out of sync.
  log "restarting BFF only on :$BFF_PORT"
  BFF_PID_FILE="$LOG_DIR/bff.pid"
  if [ -f "$BFF_PID_FILE" ] && kill -0 "$(cat "$BFF_PID_FILE" 2>/dev/null)" 2>/dev/null; then
    kill "$(cat "$BFF_PID_FILE")" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$(cat "$BFF_PID_FILE" 2>/dev/null)" 2>/dev/null || break
      sleep 1
    done
    kill -9 "$(cat "$BFF_PID_FILE" 2>/dev/null)" 2>/dev/null || true
    rm -f "$BFF_PID_FILE"
  fi
  # Fallback: kill any uvicorn bff.main process on the port.
  if command -v lsof >/dev/null 2>&1; then
    PORT_PIDS="$(lsof -tiTCP:"$BFF_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    for _pid in $PORT_PIDS; do
      if ps -p "$_pid" -o args= 2>/dev/null | grep -qE 'uvicorn.*bff\.main'; then
        kill "$_pid" 2>/dev/null || true
        sleep 1
        kill -9 "$_pid" 2>/dev/null || true
      fi
    done
  fi
  # Re-launch via forge-up.sh — it will skip agent-server + Next.js because
  # they are still listening, and start only the BFF.
  bash "$REPO_ROOT/scripts/forge-up.sh"
else
  log "stopping all Forge-OH processes"
  bash "$REPO_ROOT/scripts/forge-down.sh"
  # Small settling window: forge-down uses SIGKILL fallbacks and ports
  # need a tick to free before forge-up tries to bind them.
  sleep 1
  log "starting all Forge-OH processes"
  bash "$REPO_ROOT/scripts/forge-up.sh"
fi

# --frontend is currently a sentinel — forge-down/forge-up already handle
# it in the full-restart path. The flag exists so callers can express
# intent without needing to remember that.
if [ "$FRONTEND" -eq 1 ] && [ "$BFF_ONLY" -eq 1 ]; then
  printf '\033[33m[forge-restart]\033[0m --frontend has no effect with --bff-only\n'
fi

if [ "$SHOW_STATUS" -eq 1 ]; then
  echo
  bash "$REPO_ROOT/scripts/forge-status.sh" || true
fi
