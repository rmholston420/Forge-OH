#!/usr/bin/env bash
#
# Stage 6.3 — crash-and-resume smoke test for the idempotency ledger.
#
# Scenario:
#   1. Boot BFF on a throwaway port with a temporary ledger DB.
#   2. Post /api/idempotency/mark for (conv, leaf, tool, args).
#   3. Confirm /api/idempotency/check returns completed=true, cached present.
#   4. SIGKILL the BFF (simulates a real crash — no lifespan shutdown hook,
#      no graceful close of the aiosqlite connection).
#   5. Boot a fresh BFF on the same port, pointing at the same on-disk DB.
#   6. Post /api/idempotency/check with the same key material.
#   7. Assert completed=true still holds and the cached payload survived.
#
# Prints PASS / FAIL and exits with the appropriate status.
#
# Requirements on Colossus:
#   * .oh-venv activated (pytest, uvicorn, aiosqlite installed).
#   * curl, jq, python3.
#
# Env overrides:
#   FORGE_TEST_LEDGER_PORT (default 18191)
#   FORGE_TEST_LEDGER_DIR  (default $(mktemp -d))

set -uo pipefail

PORT="${FORGE_TEST_LEDGER_PORT:-18191}"
BASE_URL="http://127.0.0.1:${PORT}"
TEST_DIR="${FORGE_TEST_LEDGER_DIR:-$(mktemp -d -t forge-ledger-XXXXXX)}"
DATA_DIR="${TEST_DIR}/data"
LOG_DIR="${TEST_DIR}/logs"
LEDGER_DB="${DATA_DIR}/idempotency_ledger.db"

mkdir -p "$DATA_DIR" "$LOG_DIR"

# Small dedicated FastAPI app that mounts only what we need to keep the
# harness independent of the full BFF surface (which pulls in memory,
# gpu, etc.).  Written to disk so uvicorn can import it.
APP_MODULE_DIR="${TEST_DIR}/harness"
mkdir -p "$APP_MODULE_DIR"
cat >"${APP_MODULE_DIR}/ledger_only_app.py" <<'PY'
"""Minimal FastAPI app: idempotency ledger + endpoint only.

Used by scripts/test-crash-resume.sh to exercise the durable ledger in
isolation.  A crash of this process must leave the SQLite DB intact so
a fresh process observes the same completed rows.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bff.routers import idempotency as idempotency_router
from bff.services import idempotency_ledger


@asynccontextmanager
async def lifespan(app: FastAPI):
    await idempotency_ledger.init_db(app)
    yield
    await idempotency_ledger.close_db(app)


app = FastAPI(lifespan=lifespan)
app.include_router(idempotency_router.router, prefix="/api")
PY

pushd "$(git rev-parse --show-toplevel)" >/dev/null

# Point DB_PATH at our throwaway location by exporting env the module reads.
# The ledger uses module-level DB_PATH; we override via a small
# sitecustomize-style shim so the fresh process picks the same path.
export PYTHONPATH="${APP_MODULE_DIR}:${PYTHONPATH:-}"
export FORGE_LEDGER_DB_PATH="$LEDGER_DB"

# The ledger reads DB_PATH from module attribute; we monkeypatch it via an
# import-time hook by prepending a tiny sitecustomize.
cat >"${APP_MODULE_DIR}/sitecustomize.py" <<'PY'
import os
from pathlib import Path

override = os.environ.get("FORGE_LEDGER_DB_PATH")
if override:
    from bff.services import idempotency_ledger
    idempotency_ledger.DB_PATH = Path(override)
PY

start_bff() {
  local label="$1"
  echo "[crash-resume] starting BFF ($label) on :${PORT}, log=${LOG_DIR}/${label}.log"
  nohup uvicorn ledger_only_app:app \
    --host 127.0.0.1 --port "$PORT" \
    >"${LOG_DIR}/${label}.log" 2>&1 &
  local pid=$!
  echo "$pid" >"${TEST_DIR}/${label}.pid"

  # Wait for readiness.
  local deadline=$(( $(date +%s) + 20 ))
  while (( $(date +%s) < deadline )); do
    if curl -fsS -o /dev/null "${BASE_URL}/api/idempotency/check" \
        -H 'content-type: application/json' \
        -d '{"conversation_id":"probe","tool_name":"probe","arguments":{}}' 2>/dev/null; then
      echo "[crash-resume] BFF ($label) ready."
      return 0
    fi
    sleep 0.3
  done
  echo "[crash-resume] BFF ($label) failed to become ready:"
  tail -40 "${LOG_DIR}/${label}.log" || true
  return 1
}

stop_bff_hard() {
  local label="$1"
  local pidfile="${TEST_DIR}/${label}.pid"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    echo "[crash-resume] SIGKILLing BFF ($label) pid=$pid"
    kill -9 "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    rm -f "$pidfile"
  fi
}

cleanup() {
  stop_bff_hard "pre-crash" || true
  stop_bff_hard "post-crash" || true
}
trap cleanup EXIT

# --- Phase 1: pre-crash --------------------------------------------------
start_bff "pre-crash" || exit 1

CONV_ID="crash-resume-conv-1"
LEAF_ID="crash-resume-leaf-1"
TOOL_NAME="write_note"
ARGS='{"title":"crash-resume-note","body":"payload"}'

MARK_BODY=$(cat <<JSON
{
  "conversation_id": "${CONV_ID}",
  "leaf_event_id":   "${LEAF_ID}",
  "tool_name":       "${TOOL_NAME}",
  "arguments":       ${ARGS},
  "result_summary":  "phase-1 mark",
  "result_json":     {"phase": 1, "path": "/tmp/example.txt"}
}
JSON
)

mark_resp=$(curl -fsS -X POST "${BASE_URL}/api/idempotency/mark" \
  -H 'content-type: application/json' -d "$MARK_BODY")
echo "[crash-resume] pre-crash mark response: $mark_resp"
first_recorded=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['data']['recorded'])" "$mark_resp")
if [[ "$first_recorded" != "True" ]]; then
  echo "[crash-resume] FAIL: pre-crash mark did not report recorded=True"
  exit 2
fi

CHECK_BODY=$(cat <<JSON
{
  "conversation_id": "${CONV_ID}",
  "leaf_event_id":   "${LEAF_ID}",
  "tool_name":       "${TOOL_NAME}",
  "arguments":       ${ARGS}
}
JSON
)
check_resp=$(curl -fsS -X POST "${BASE_URL}/api/idempotency/check" \
  -H 'content-type: application/json' -d "$CHECK_BODY")
echo "[crash-resume] pre-crash check response: $check_resp"
pre_completed=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['data']['completed'])" "$check_resp")
if [[ "$pre_completed" != "True" ]]; then
  echo "[crash-resume] FAIL: pre-crash check did not report completed=True"
  exit 3
fi

# --- Phase 2: simulate crash --------------------------------------------
stop_bff_hard "pre-crash"

# Ensure DB survived on disk.
if [[ ! -s "$LEDGER_DB" ]]; then
  echo "[crash-resume] FAIL: ledger DB missing after crash: $LEDGER_DB"
  exit 4
fi

# --- Phase 3: resume with a fresh process -------------------------------
start_bff "post-crash" || exit 5

resume_resp=$(curl -fsS -X POST "${BASE_URL}/api/idempotency/check" \
  -H 'content-type: application/json' -d "$CHECK_BODY")
echo "[crash-resume] post-crash check response: $resume_resp"

post_completed=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['data']['completed'])" "$resume_resp")
post_result_json=$(python3 -c "import json,sys;print(json.dumps(json.loads(sys.argv[1])['data']['cached']['result_json']))" "$resume_resp")

if [[ "$post_completed" != "True" ]]; then
  echo "[crash-resume] FAIL: post-crash check did not report completed=True"
  exit 6
fi
if [[ "$post_result_json" != '{"phase": 1, "path": "/tmp/example.txt"}' ]]; then
  echo "[crash-resume] FAIL: cached result_json did not survive crash: $post_result_json"
  exit 7
fi

# --- Phase 4: replay mark returns recorded=false ------------------------
replay_resp=$(curl -fsS -X POST "${BASE_URL}/api/idempotency/mark" \
  -H 'content-type: application/json' -d "$MARK_BODY")
echo "[crash-resume] post-crash replay-mark response: $replay_resp"
replay_recorded=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['data']['recorded'])" "$replay_resp")
if [[ "$replay_recorded" != "False" ]]; then
  echo "[crash-resume] FAIL: post-crash replay mark expected recorded=False, got: $replay_resp"
  exit 8
fi
echo "[crash-resume] phase 4 OK: replay mark reported recorded=false (ledger already had the row)"

echo
echo "[crash-resume] PASS"
echo "  ledger DB: $LEDGER_DB"
echo "  test dir:  $TEST_DIR"
popd >/dev/null
