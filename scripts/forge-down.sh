#!/usr/bin/env bash
# forge-down.sh — stop everything forge-up.sh started
#
# Kills PIDs stored in .forge-logs/*.pid, then any lingering listeners
# on the known ports as a fallback. Also removes the legacy agent-server
# docker container if one is still around from a pre-Slice-F.9 topology.
#
# Usage: bash scripts/forge-down.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/.forge-logs"

BFF_PORT="${BFF_PORT:-8081}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"

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

kill_by_pattern() {
  # Kill every process whose full command line matches an ERE. Used to
  # reap detached children (e.g. `next-server` spawned by `pnpm dev` and
  # kept alive when the pnpm parent takes SIGTERM). pgrep -f matches
  # against the full argv, which is exactly what we want.
  local pattern="$1" name="$2"
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  local pids
  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    log "killing $name processes matching '$pattern' (pids: $(echo $pids | tr '\n' ' '))"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

# ---- Frontend + BFF + agent-server (pidfile path) -----------------------
kill_pidfile "$LOG_DIR/frontend.pid"     "Next.js"
kill_pidfile "$LOG_DIR/bff.pid"          "BFF"
kill_pidfile "$LOG_DIR/agent-server.pid" "agent-server"

# ---- Pattern fallback for detached children -----------------------------
# pnpm dev spawns next-server as a detached child; killing the pnpm parent
# leaves the child holding :3000. Match on argv to catch the orphan.
kill_by_pattern 'next-server|pnpm.*dev|node.*next/dist/bin/next' 'Next.js'
# uvicorn workers under --reload spawn a subprocess; the parent hands off
# the listen socket. If pidfile pointed at a dead parent we may leave the
# child alive on :8081. Match on argv to be safe.
kill_by_pattern 'uvicorn.*bff\.main' 'BFF'
# agent-server rarely leaves orphans (no --reload), but symmetrical guard.
kill_by_pattern 'openhands\.agent_server' 'agent-server'

# ---- Port fallback for anything still bound -----------------------------
kill_port    "$FRONTEND_PORT"          "Next.js"
kill_port    "$BFF_PORT"               "BFF"
kill_port    "$AGENT_PORT"             "agent-server"

# ---- Legacy docker container cleanup ------------------------------------
# The pre-F.9 topology ran the agent-server as a docker container. If one
# is still around (e.g. a stale process from before the topology change),
# tear it down so the port doesn't stay held.
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^forge-oh-agent-server$'; then
    log "removing legacy docker container forge-oh-agent-server"
    docker stop forge-oh-agent-server >/dev/null 2>&1 || true
    docker rm   forge-oh-agent-server >/dev/null 2>&1 || true
  fi
fi

log "✅ Forge-OH stopped"
