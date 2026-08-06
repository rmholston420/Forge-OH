#!/usr/bin/env bash
# scripts/start-host-services.sh — bring up Forge-OH host-side inference
# dependencies (Ollama + vLLM planner container + vLLM coder). Idempotent:
# re-running is a no-op if everything is already healthy.
#
# Deliberately does NOT start:
#   * agent-server, BFF, Next.js  — that's scripts/forge-up.sh
#   * docker-compose (bff + qdrant) — `docker compose up -d`
#   * SearXNG                      — `docker compose -f ops/compose/searxng.yml up -d`
#   * Kosmos-owned DozerDB          — external to Forge-OH
#
# See docs/deployment-topology.md for the full split.

set -uo pipefail

FORGE_DIR="${FORGE_DIR:-$HOME/dev/forge-oh}"
cd "$FORGE_DIR" || { echo "✗ cannot cd to $FORGE_DIR" >&2; exit 1; }

log()  { printf '\033[1;36m→\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; }

# ---- 1. Ollama (systemd or user service) ----------------------------------

log "Ollama (11434)"
if curl -sf --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  ok "already up"
else
  if command -v systemctl >/dev/null && systemctl is-enabled --quiet ollama 2>/dev/null; then
    sudo systemctl start ollama || warn "systemctl start ollama returned non-zero"
  else
    nohup ollama serve >>"$HOME/.forge-oh/ollama.log" 2>&1 &
  fi
  for _ in 1 2 3 4 5; do
    sleep 1
    curl -sf --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && { ok "started"; break; }
  done
  curl -sf --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || err "Ollama did not come up on 11434"
fi

# ---- 2. vLLM planner container (host-managed, port 8511) ------------------

log "vLLM planner (8511)"
if curl -sf --max-time 2 http://127.0.0.1:8511/v1/models >/dev/null 2>&1; then
  ok "already up"
elif [[ -x "$FORGE_DIR/scripts/vllm_start.sh" ]]; then
  log "invoking scripts/vllm_start.sh (cold-start can take ~3 min)"
  bash "$FORGE_DIR/scripts/vllm_start.sh" || warn "vllm_start.sh returned non-zero"
else
  warn "scripts/vllm_start.sh not found — start the planner container manually"
fi

# ---- 3. vLLM coder (host process, port 8000) ------------------------------

log "vLLM coder (8000)"
if curl -sf --max-time 2 http://127.0.0.1:8000/v1/models >/dev/null 2>&1; then
  ok "already up"
elif [[ -x "$FORGE_DIR/scripts/vllm-coder-bringup.sh" ]]; then
  log "invoking scripts/vllm-coder-bringup.sh"
  bash "$FORGE_DIR/scripts/vllm-coder-bringup.sh" || warn "vllm-coder-bringup.sh returned non-zero"
else
  warn "scripts/vllm-coder-bringup.sh not found — start the coder manually"
fi

# ---- 4. Summary -----------------------------------------------------------

echo
log "Host-service status:"
for pair in "Ollama:11434:/api/tags" "vLLM-planner:8511:/v1/models" "vLLM-coder:8000:/v1/models"; do
  IFS=':' read -r name port path <<<"$pair"
  if curl -sf --max-time 2 "http://127.0.0.1:${port}${path}" >/dev/null 2>&1; then
    ok "$name (:$port)"
  else
    err "$name (:$port) — unreachable"
  fi
done

# Non-zero exit if any of the three is unreachable, so this can gate other
# scripts.
for pair in "11434:/api/tags" "8511:/v1/models" "8000:/v1/models"; do
  IFS=':' read -r port path <<<"$pair"
  curl -sf --max-time 2 "http://127.0.0.1:${port}${path}" >/dev/null 2>&1 || exit 1
done
exit 0
