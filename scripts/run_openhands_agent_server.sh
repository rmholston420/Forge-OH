#!/usr/bin/env bash
# run_openhands_agent_server.sh — foreground launcher for the OpenHands
# agent-server in .oh-venv.
#
# Slice F.9: this used to launch a docker container. We now run the
# agent-server directly in .oh-venv so:
#   * openhands_tools_ext is importable from the SDK subprocesses that
#     spawn our STOP hooks (verify + trajectory).
#   * Workspace paths written by the agent land on the host, not inside
#     a container.
#   * The topology matches the local-first, single-user project brief.
#
# forge-up.sh is the normal entry point (starts it in the background
# with a pidfile). Use this script only when you want to tail the
# server directly in the foreground.
#
# Usage: bash scripts/run_openhands_agent_server.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

OPENHANDS_AGENT_SERVER_HOST="${OPENHANDS_AGENT_SERVER_HOST:-127.0.0.1}"
OPENHANDS_AGENT_SERVER_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"

if [ ! -f .oh-venv/bin/activate ]; then
  echo "error: .oh-venv not found at $REPO_ROOT/.oh-venv" 1>&2
  echo "  create it with: python3.12 -m venv .oh-venv && .oh-venv/bin/pip install -e ." 1>&2
  exit 1
fi

# shellcheck disable=SC1091
source .oh-venv/bin/activate

echo "Starting OpenHands agent-server on ${OPENHANDS_AGENT_SERVER_HOST}:${OPENHANDS_AGENT_SERVER_PORT} (.oh-venv)..."

exec python -m openhands.agent_server \
  --host "$OPENHANDS_AGENT_SERVER_HOST" \
  --port "$OPENHANDS_AGENT_SERVER_PORT"
