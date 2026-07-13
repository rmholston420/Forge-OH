#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

OPENHANDS_AGENT_SERVER_HOST="${OPENHANDS_AGENT_SERVER_HOST:-127.0.0.1}"
OPENHANDS_AGENT_SERVER_PORT="${OPENHANDS_AGENT_SERVER_PORT:-8081}"

echo "Starting OpenHands SDK Agent Server ${OPENHANDS_SDK_VERSION:-(version from env)} on ${OPENHANDS_AGENT_SERVER_HOST}:${OPENHANDS_AGENT_SERVER_PORT}..."

python -m openhands_sdk.agent_server \
  --host "${OPENHANDS_AGENT_SERVER_HOST}" \
  --port "${OPENHANDS_AGENT_SERVER_PORT}"
