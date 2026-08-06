#!/usr/bin/env bash
# forge-up.sh — start Forge-OH: agent-server (.oh-venv), BFF (uvicorn), Next.js
#
# Slice F.9 topology change: agent-server now runs directly in .oh-venv
# instead of the ghcr.io/openhands/agent-server docker image, because:
#   1. The stock docker image does not ship openhands_tools_ext, so our
#      STOP hooks (verify + trajectory) would silently no-op.
#   2. The stock image has no bind mount to the host workspace, so any
#      workspace-relative file the agent (or a hook) writes would end up
#      inside the container instead of on the host.
#   3. This project is local-first, single-user (see AGENTS.md / project
#      instructions), so a shared control-plane container is unwarranted
#      overhead.
#
# Idempotent: if a service is already listening, it is left alone.
# Logs go to .forge-logs/{agent-server,bff,frontend}.log
# PIDs are stored in .forge-logs/{agent-server,bff,frontend}.pid
#
# Usage: bash scripts/forge-up.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/.forge-logs"
mkdir -p "$LOG_DIR"

BFF_PORT="${BFF_PORT:-8081}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"

log()  { printf '\033[36m[forge-up]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[forge-up]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[forge-up]\033[0m %s\n' "$*" 1>&2; }

port_in_use() {
  # Return 0 if $1 is listening
  ss -ltn "sport = :$1" 2>/dev/null | tail -n +2 | grep -q ':'
}

wait_for_port() {
  local port="$1" name="$2" timeout="${3:-30}"
  local waited=0
  until port_in_use "$port"; do
    sleep 1
    waited=$((waited + 1))
    if [ "$waited" -ge "$timeout" ]; then
      err "$name did not open port $port within ${timeout}s"
      return 1
    fi
  done
  log "$name ready on :$port (after ${waited}s)"
}

# Activate .oh-venv up front — both agent-server and BFF need it, and
# hooks spawned by the agent-server inherit its interpreter.
if [ -f ".oh-venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .oh-venv/bin/activate
else
  err ".oh-venv not found at $REPO_ROOT/.oh-venv"
  err "  create it with: python3.12 -m venv .oh-venv && .oh-venv/bin/pip install -e ."
  exit 1
fi

# Pin the trajectory DB to a single path shared by the BFF, the
# agent-server, and the STOP hooks. Without this, the hook (which runs
# with OPENHANDS_PROJECT_DIR set) would write to
# $WORKSPACE/.forge-oh/trajectories.db while the BFF (no project dir)
# would read ~/.forge-oh/trajectories.db, and they'd never see each
# other's data.
export FORGE_OH_TRAJECTORY_DB="${FORGE_OH_TRAJECTORY_DB:-$HOME/.forge-oh/trajectories.db}"
mkdir -p "$(dirname "$FORGE_OH_TRAJECTORY_DB")"

# ---- 1. Agent-server (.oh-venv, host process) ----------------------------
# Same interpreter as the BFF, so `python -m openhands_tools_ext.verify.hook`
# and `python -m openhands_tools_ext.trajectory.hook` resolve correctly when
# the SDK spawns them as STOP hook subprocesses.
AGENT_PID_FILE="$LOG_DIR/agent-server.pid"

# Kill any leftover docker container from the previous topology, so it
# doesn't fight for :8090.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^forge-oh-agent-server$'; then
  log "removing legacy docker container forge-oh-agent-server"
  docker rm -f forge-oh-agent-server >/dev/null 2>&1 || true
fi

if [ -f "$AGENT_PID_FILE" ] && kill -0 "$(cat "$AGENT_PID_FILE" 2>/dev/null)" 2>/dev/null; then
  log "agent-server already running (pid $(cat "$AGENT_PID_FILE"))"
elif port_in_use "$AGENT_PORT"; then
  warn "port $AGENT_PORT already in use by non-forge process; leaving it alone"
else
  log "starting agent-server on :${AGENT_PORT} (.oh-venv)"
  # OPENHANDS_SUPPRESS_BANNER=1 keeps the startup log clean.
  # Bind to 127.0.0.1 explicitly — this is a single-user local box.
  # --import-modules preloads Forge-OH-owned tool modules so their
  # top-level ``register_tool(...)`` calls run before the first
  # conversation is created (Stage 5.6b: consult_memory).
  OPENHANDS_SUPPRESS_BANNER=1 \
    nohup python -m openhands.agent_server \
      --host 127.0.0.1 --port "$AGENT_PORT" \
      --import-modules openhands_tools_ext.memory.tools.consult_memory \
      --import-modules openhands_tools_ext.search.tools.search_web \
      >>"$LOG_DIR/agent-server.log" 2>&1 &
  echo $! > "$AGENT_PID_FILE"
  wait_for_port "$AGENT_PORT" "agent-server" 60 || true
fi

# ---- 2. BFF (uvicorn) ----------------------------------------------------
# Local-first, single-user: we ALWAYS restart the BFF here so that any code
# changes since the last `forge-up` are actually running. `--reload` handles
# in-flight edits; the explicit kill covers the case where the previous run
# had `--reload` disabled or the process is wedged.
BFF_PID_FILE="$LOG_DIR/bff.pid"
# Kill by pid-file first (clean path), then fall back to killing whoever is on
# the port (covers the case where a previous run launched uvicorn without a
# pid file, or the pid file was lost). Only kill if the process on the port
# looks like our uvicorn BFF, to avoid nuking an unrelated dev process.
if [ -f "$BFF_PID_FILE" ] && kill -0 "$(cat "$BFF_PID_FILE" 2>/dev/null)" 2>/dev/null; then
  log "stopping previous BFF (pid $(cat "$BFF_PID_FILE"))"
  kill "$(cat "$BFF_PID_FILE")" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    kill -0 "$(cat "$BFF_PID_FILE" 2>/dev/null)" 2>/dev/null || break
    sleep 1
  done
  kill -9 "$(cat "$BFF_PID_FILE" 2>/dev/null)" 2>/dev/null || true
  rm -f "$BFF_PID_FILE"
fi
if port_in_use "$BFF_PORT"; then
  # Discover PIDs on the port; check if any looks like our BFF (uvicorn + bff.main).
  BFF_PORT_PIDS="$(ss -ltnp "sport = :$BFF_PORT" 2>/dev/null \
    | awk 'NR>1 {print $NF}' \
    | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
  if [ -n "$BFF_PORT_PIDS" ]; then
    KILLED=0
    for _pid in $BFF_PORT_PIDS; do
      if ps -p "$_pid" -o args= 2>/dev/null | grep -qE 'uvicorn.*bff\.main'; then
        log "stopping stale BFF on :$BFF_PORT (pid $_pid)"
        kill "$_pid" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
          kill -0 "$_pid" 2>/dev/null || break
          sleep 1
        done
        kill -9 "$_pid" 2>/dev/null || true
        KILLED=1
      fi
    done
    if [ "$KILLED" -eq 0 ]; then
      warn "BFF port $BFF_PORT held by non-BFF process; leaving it alone"
    fi
  else
    warn "BFF port $BFF_PORT in use but PID unknown; leaving it alone"
  fi
  # give the socket a moment to free
  sleep 1
fi
if ! port_in_use "$BFF_PORT"; then
  log "starting BFF on :${BFF_PORT} (with --reload)"
  # Stage 5.6a (ADR-024 K1): source .env.neo4j when present so the lazy
  # MemoryPort singleton composes on first request. Missing password is
  # non-fatal — the memory router 503s and the frontend renders a
  # warning banner — but visual specs require this env to be set.
  if [ -f "$REPO_ROOT/.env.neo4j" ]; then
    log "sourcing .env.neo4j for BFF memory composition"
    set -a; . "$REPO_ROOT/.env.neo4j"; set +a
  else
    warn ".env.neo4j not found; BFF will boot without MemoryPort"
  fi
  nohup uvicorn bff.main:app_with_sio \
    --host 127.0.0.1 --port "$BFF_PORT" \
    --reload --reload-dir bff \
    >>"$LOG_DIR/bff.log" 2>&1 &
  echo $! > "$BFF_PID_FILE"
  wait_for_port "$BFF_PORT" "BFF" 20
fi

# ---- 3. Frontend (Next.js) -----------------------------------------------
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
if port_in_use "$FRONTEND_PORT"; then
  log "frontend already listening on :$FRONTEND_PORT"
else
  log "starting Next.js on :${FRONTEND_PORT}"
  nohup pnpm dev >>"$LOG_DIR/frontend.log" 2>&1 &
  echo $! > "$FRONTEND_PID_FILE"
  wait_for_port "$FRONTEND_PORT" "Next.js" 60
fi

echo
log "✅ Forge-OH is up"
printf '  agent-server  http://127.0.0.1:%s   (log: %s)\n' "$AGENT_PORT" "$LOG_DIR/agent-server.log"
printf '  BFF           http://127.0.0.1:%s   (log: %s)\n' "$BFF_PORT" "$LOG_DIR/bff.log"
printf '  Next.js       http://localhost:%s      (log: %s)\n' "$FRONTEND_PORT" "$LOG_DIR/frontend.log"
