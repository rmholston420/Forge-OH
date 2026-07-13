#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

OPENHANDS_AGENT_SERVER_HOST="${OPENHANDS_AGENT_SERVER_HOST:-127.0.0.1}"
OPENHANDS_AGENT_SERVER_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8090}"

echo "Starting external OpenHands Agent Server on ${OPENHANDS_AGENT_SERVER_HOST}:${OPENHANDS_AGENT_SERVER_PORT} via Docker..."

docker run --rm -it \
  -p "${OPENHANDS_AGENT_SERVER_PORT}:8000" \
  ghcr.io/openhands/agent-server:latest-python
