#!/usr/bin/env bash
# F.19.1a — vLLM swap-on-demand supervisor.
#
# Enforces the ADR-009 §3a topology: exactly one of the coder (:8501) or
# planner (:8511) vLLM launcher is running at a time on Colossus. On the
# single RTX 5090 (~30 GiB usable VRAM) both models cannot be co-resident.
#
# Behavior:
#   * `up coder`    — stop planner if running, start coder, wait for
#                     readiness on :8501/v1/models.
#   * `up planner`  — stop coder if running, start planner, wait for
#                     readiness on :8511/v1/models.
#   * `down`        — stop whichever role (if any) is running.
#   * `status`      — print which role (coder|planner|none) is live and
#                     its /v1/models readiness. Exit 0=coder, 1=planner,
#                     2=none, 3=broken (port open but /v1/models fails).
#   * `ensure <role>` — no-op if the requested role is already live and
#                       ready; otherwise same as `up <role>`. This is the
#                       call the BFF router uses on cache-miss.
#
# Runtime:
#   * F.19 uses the pinned vLLM Docker image (matches the bench). Each
#     role runs in a named container: `forge-vllm-coder` on :8501 and
#     `forge-vllm-planner` on :8511. Stopping a role does `docker rm -f`
#     plus a `fuser -k` belt-and-braces to clear any stale native-venv
#     process still holding the port.
#   * Native venv (~/venv/vllm-new, vLLM 0.10.2) does NOT support the
#     qwen3_5_moe arch used by both role models. Upgrading the native
#     venv to vLLM ≥ 0.26.0 is deferred to F.19.5.
#
# Notes:
#   * "Which role is live" is decided by which of :8501 / :8511 responds
#     to /v1/models with data. If both respond (should not happen on
#     Colossus but is possible in a shared-lab scenario), status prints
#     "both" and exits 3.
#   * The per-role log under ~/.forge-oh/ captures the `docker run`
#     handshake only. Container runtime logs live in
#     `docker logs -f forge-vllm-{coder,planner}`.
#
# Env:
#   FORGE_OH_ROOT      default = git rev-parse --show-toplevel from
#                      the script's directory. Used to locate the
#                      launcher scripts. Override for out-of-tree tests.
#   VLLM_READY_TIMEOUT default 300 (seconds). Bounded wait for the
#                      newly-launched role's /v1/models to return data.

# NOTE: no `set -e` at top level (per user preference — paste-block safe).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORGE_OH_ROOT="${FORGE_OH_ROOT:-$(cd "$SCRIPT_DIR/.." && git rev-parse --show-toplevel 2>/dev/null || cd "$SCRIPT_DIR/.." && pwd)}"

CODER_PORT="${VLLM_CODER_PORT:-8501}"
PLANNER_PORT="${VLLM_PLANNER_PORT:-8511}"
CODER_LOG="${VLLM_CODER_LOG:-$HOME/.forge-oh/vllm-coder.log}"
PLANNER_LOG="${VLLM_PLANNER_LOG:-$HOME/.forge-oh/vllm-planner.log}"
READY_TIMEOUT="${VLLM_READY_TIMEOUT:-300}"

CODER_LAUNCHER="$SCRIPT_DIR/vllm_launch_coder.sh"
PLANNER_LAUNCHER="$SCRIPT_DIR/vllm_launch_planner.sh"
VLLM_STOP="$FORGE_OH_ROOT/scripts/vllm_stop.sh"

# Docker container names (must match launcher scripts).
CODER_CONTAINER="${FORGE_VLLM_CODER_CONTAINER:-forge-vllm-coder}"
PLANNER_CONTAINER="${FORGE_VLLM_PLANNER_CONTAINER:-forge-vllm-planner}"

mkdir -p "$HOME/.forge-oh"

# --- Helpers ---------------------------------------------------------------

_probe_ready() {
    # Args: PORT. Returns 0 if /v1/models returns 200 with data.
    local port="$1"
    local body
    body=$(curl -sf --max-time 3 "http://127.0.0.1:${port}/v1/models" 2>/dev/null)
    [ -z "$body" ] && return 1
    # Cheap presence check for `"data"` array with at least one entry.
    echo "$body" | grep -q '"data"[[:space:]]*:[[:space:]]*\[[[:space:]]*{' || return 1
    return 0
}

_stop_role() {
    # Args: ROLE. Removes the Docker container for the role and, as a
    # belt-and-braces measure, kills any process still bound to the port
    # (e.g. a stale native-venv vllm from an F.18-era session).
    local role="$1" container port
    case "$role" in
        coder)
            container="$CODER_CONTAINER"; port="$CODER_PORT" ;;
        planner)
            container="$PLANNER_CONTAINER"; port="$PLANNER_PORT" ;;
        *)
            return 2 ;;
    esac
    docker rm -f "$container" >/dev/null 2>&1 || true
    # If a native-venv (or unrelated) process is still on the port, free it.
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    fi
    # Ensure the port has actually been released before we return — TIME_WAIT
    # sockets from a previous serve can otherwise re-bind-fail the next launch.
    local waited=0
    while [ $waited -lt 10 ]; do
        if ! ss -ltn "sport = :${port}" 2>/dev/null | grep -q LISTEN; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 0
}

_which_role_live() {
    # Prints one of: coder | planner | both | none.
    local c=1 p=1
    _probe_ready "$CODER_PORT" && c=0
    _probe_ready "$PLANNER_PORT" && p=0
    if [ $c -eq 0 ] && [ $p -eq 0 ]; then
        echo "both"
    elif [ $c -eq 0 ]; then
        echo "coder"
    elif [ $p -eq 0 ]; then
        echo "planner"
    else
        echo "none"
    fi
}

_wait_ready() {
    # Args: PORT ROLE. Poll /v1/models every 2s up to READY_TIMEOUT.
    local port="$1" role="$2" waited=0
    while [ $waited -lt "$READY_TIMEOUT" ]; do
        if _probe_ready "$port"; then
            echo "[supervisor] $role READY on :$port after ${waited}s"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    echo "[supervisor] TIMEOUT waiting for $role on :$port after ${READY_TIMEOUT}s" >&2
    return 1
}

_launch() {
    # Args: LAUNCHER LOG.
    # Docker launchers `docker run -d` and return immediately. We run them
    # in the foreground, capture stdout+stderr into LOG, and return their
    # exit code so a bad docker invocation short-circuits before the
    # readiness wait.
    local launcher="$1" log="$2"
    if [ ! -x "$launcher" ]; then
        echo "[supervisor] launcher not executable: $launcher" >&2
        return 1
    fi
    "$launcher" > "$log" 2>&1
    local rc=$?
    if [ $rc -ne 0 ]; then
        echo "[supervisor] $(basename "$launcher") exited $rc (see $log)" >&2
        return $rc
    fi
    echo "[supervisor] $(basename "$launcher") started (log: $log)"
    return 0
}

# --- Commands --------------------------------------------------------------

cmd_up() {
    local role="$1"
    case "$role" in
        coder)
            _stop_role "planner"
            _stop_role "coder"  # kill any prior coder container/socket too
            _launch "$CODER_LAUNCHER" "$CODER_LOG" || return 1
            _wait_ready "$CODER_PORT" "coder" || return 1
            ;;
        planner)
            _stop_role "coder"
            _stop_role "planner"
            _launch "$PLANNER_LAUNCHER" "$PLANNER_LOG" || return 1
            _wait_ready "$PLANNER_PORT" "planner" || return 1
            ;;
        *)
            echo "usage: $0 up {coder|planner}" >&2
            return 2
            ;;
    esac
}

cmd_ensure() {
    local role="$1"
    case "$role" in
        coder|planner) ;;
        *)
            echo "usage: $0 ensure {coder|planner}" >&2
            return 2
            ;;
    esac
    local live
    live=$(_which_role_live)
    if [ "$live" = "$role" ]; then
        echo "[supervisor] $role already live"
        return 0
    fi
    cmd_up "$role"
}

cmd_down() {
    _stop_role "coder"
    _stop_role "planner"
    echo "[supervisor] both roles down"
}

cmd_status() {
    local live
    live=$(_which_role_live)
    echo "coder_port    : $CODER_PORT"
    echo "planner_port  : $PLANNER_PORT"
    echo "live_role     : $live"
    case "$live" in
        coder)   return 0 ;;
        planner) return 1 ;;
        none)    return 2 ;;
        both)    echo "[supervisor] WARN: both ports responding — ADR-009 §3a violation" >&2
                 return 3 ;;
    esac
}

# --- Dispatch --------------------------------------------------------------

case "${1:-}" in
    up)     shift; cmd_up "${1:-}" ;;
    ensure) shift; cmd_ensure "${1:-}" ;;
    down)   cmd_down ;;
    status) cmd_status ;;
    *)
        cat >&2 <<USAGE
vLLM swap-on-demand supervisor (ADR-009 §3a).

Usage:
  $0 up {coder|planner}      Stop the other role, start this one, wait ready.
  $0 ensure {coder|planner}  No-op if already live+ready; else same as 'up'.
  $0 down                    Stop both roles.
  $0 status                  Print live role. Exit: 0=coder 1=planner
                             2=none 3=broken/both.

Env: VLLM_CODER_PORT (default 8501), VLLM_PLANNER_PORT (8511),
     VLLM_READY_TIMEOUT (300s), VLLM_CODER_LOG, VLLM_PLANNER_LOG.
USAGE
        exit 2
        ;;
esac
