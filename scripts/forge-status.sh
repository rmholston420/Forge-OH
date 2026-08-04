#!/usr/bin/env bash
# forge-status.sh — one-glance state of Forge-OH processes and ports
#
# Prints, for each component (agent-server, BFF, Next.js):
#   port | listening? | pidfile pid | pid alive? | pid on port
#
# Exit code 0 if all three are healthy (listening AND pidfile-alive AND
# the process on the port matches the pidfile). Exit code 1 otherwise.
#
# Usage: bash scripts/forge-status.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_ROOT/.forge-logs"

BFF_PORT="${BFF_PORT:-8081}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"

green()  { printf '\033[32m%s\033[0m' "$1"; }
red()    { printf '\033[31m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }

port_listening() {
  # 0 = listening; 1 = not
  ss -ltn "sport = :$1" 2>/dev/null | tail -n +2 | grep -q ':'
}

pid_on_port() {
  # Print the first PID listening on $1, or empty.
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -n1
  else
    ss -ltnp "sport = :$1" 2>/dev/null \
      | awk 'NR>1' \
      | grep -oE 'pid=[0-9]+' | head -n1 | cut -d= -f2
  fi
}

any_bad=0
row() {
  local name="$1" port="$2" pidfile="$3"
  local listening="" pf_pid="" pf_alive="" port_pid="" match=""
  if port_listening "$port"; then
    listening="$(green 'yes')"
  else
    listening="$(red 'no')"
    any_bad=1
  fi
  if [ -f "$pidfile" ]; then
    pf_pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "$pf_pid" ] && kill -0 "$pf_pid" 2>/dev/null; then
      pf_alive="$(green 'alive')"
    else
      pf_alive="$(red 'dead')"
      any_bad=1
    fi
  else
    pf_pid="-"
    pf_alive="$(yellow 'no pidfile')"
  fi
  port_pid="$(pid_on_port "$port" || true)"
  port_pid="${port_pid:--}"
  if [ "$pf_pid" != "-" ] && [ "$port_pid" != "-" ] && [ "$pf_pid" = "$port_pid" ]; then
    match="$(green 'match')"
  elif [ "$pf_pid" = "-" ] || [ "$port_pid" = "-" ]; then
    match="$(yellow 'n/a')"
    # Listening on the port with NO pidfile AND NO discoverable PID means an
    # orphaned or externally-launched process is holding it. That is not a
    # healthy state for a component we claim to manage — flag it red so
    # `forge-restart.sh --status` and CI-style checks don't gloss over it.
    if [ "$listening" = "$(green 'yes')" ]; then
      any_bad=1
    fi
  else
    match="$(yellow 'mismatch')"
    any_bad=1
  fi
  printf '  %-14s :%-5s  listen=%-4s  pidfile=%-8s  alive=%-16s  onport=%-8s  %s\n' \
    "$name" "$port" "$listening" "$pf_pid" "$pf_alive" "$port_pid" "$match"
}

printf '[forge-status] Forge-OH components\n'
row 'agent-server' "$AGENT_PORT" "$LOG_DIR/agent-server.pid"
row 'BFF'          "$BFF_PORT"   "$LOG_DIR/bff.pid"
row 'Next.js'      "$FRONTEND_PORT" "$LOG_DIR/frontend.pid"

if [ "$any_bad" -eq 0 ]; then
  printf '\n[forge-status] %s all three healthy\n' "$(green '✅')"
  exit 0
else
  printf '\n[forge-status] %s at least one component is not healthy\n' "$(red '❌')"
  exit 1
fi
