#!/usr/bin/env bash
# forge-down.sh — stop everything forge-up.sh started
#
# Kills PIDs stored in .forge-logs/*.pid, then any lingering listeners
# on the known ports as a fallback. Stops the agent-server docker container.
#
# Usage: bash scripts/forge-down.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/.forge-logs"

BFF_PORT="${BFF_PORT:-8081}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"
AGENT_CONTAINER="forge-oh-agent-server"

log()  { printf '\033[36m[forge-down]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[forge-down]\033[0m %s\n' "$*"; }

kill_pidfile() {
  local file="$1" name="$2"
  if [ -f "$file" ]; then
    local pid
    pid="$(cat "$file")"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      log "stopping $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    else
      warn "$name pidfile stale (pid $pid not running)"
    fi
    rm -f "$file"
  fi
}

kill_port() {
  local port="$1" name="$2"
  # Fallback: kill anything still listening on the port.
  # -t = pids only. Ignore errors when nothing matches.
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    log "killing lingering $name listener on :$port (pids: $pids)"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

# ---- Frontend + BFF ------------------------------------------------------
kill_pidfile "$LOG_DIR/frontend.pid" "Next.js"
kill_pidfile "$LOG_DIR/bff.pid"       "BFF"
kill_port    "$FRONTEND_PORT"          "Next.js"
kill_port    "$BFF_PORT"               "BFF"

# ---- Agent-server (docker) ----------------------------------------------
if docker ps --format '{{.Names}}' | grep -q "^${AGENT_CONTAINER}$"; then
  log "stopping agent-server container ${AGENT_CONTAINER}"
  docker stop "$AGENT_CONTAINER" >/dev/null 2>&1 || true
  docker rm   "$AGENT_CONTAINER" >/dev/null 2>&1 || true
else
  # Fallback: any container publishing the agent port
  local_ids="$(docker ps --filter "publish=${AGENT_PORT}" --format '{{.ID}}' 2>/dev/null || true)"
  if [ -n "$local_ids" ]; then
    log "stopping other docker container(s) on :${AGENT_PORT}: $local_ids"
    # shellcheck disable=SC2086
    docker stop $local_ids >/dev/null 2>&1 || true
  fi
fi

log "✅ Forge-OH stopped"
