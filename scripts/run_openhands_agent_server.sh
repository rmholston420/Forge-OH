#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

OPENHANDS_AGENT_SERVER_HOST="${OPENHANDS_AGENT_SERVER_HOST:-127.0.0.1}"
OPENHANDS_AGENT_SERVER_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"

echo "Starting external OpenHands Agent Server on ${OPENHANDS_AGENT_SERVER_HOST}:${OPENHANDS_AGENT_SERVER_PORT}..."
echo "NOTE: This script assumes you start the Agent Server via its own CLI or Docker image."

# Example Docker placeholder:
# docker run --rm -p "${OPENHANDS_AGENT_SERVER_PORT}:8080" openhands/agent-server:latest

echo "No concrete agent server command configured yet."
exit 1
