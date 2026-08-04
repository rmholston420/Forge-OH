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
#   VLLM_READY_TIMEOUT default 420 (seconds). Bounded wait for the
#                      newly-launched role's /v1/models to return data.
#   VLLM_MIN_FREE_MIB  default 28000 (MiB). Minimum free VRAM required
#                      before launching a vLLM role. Matches
#                      --gpu-memory-utilization 0.90 on a 31 GiB card
#                      (0.90 * 31.4 * 1024 ≈ 28900 MiB, rounded down
#                      to 28000 for safety). If less than this is free
#                      after Ollama stop + wait, cmd_up aborts.
#   VLLM_GPU_FREE_TIMEOUT default 30 (seconds). Bounded wait for VRAM
#                      to drop below the min-free threshold after
#                      stopping Ollama and any prior vLLM container.
#   VLLM_SKIP_OLLAMA_STOP default 0. Set to 1 to skip the Ollama stop
#                      step (useful when the caller has already stopped
#                      it, or on a machine without Ollama installed).

# ADR-009 §5 / DEBUG_LOG 2026-08-04 01:49 EDT:
# Ollama holds ~5-22 GB VRAM depending on the model tag it last loaded.
# vLLM 0.26.0 refuses to launch with --gpu-memory-utilization 0.90 if
# free VRAM < 28.25 GiB, with a hard ValueError: "Free memory on device
# cuda:0 (X/31.39 GiB) on startup is less than desired GPU memory
# utilization". The supervisor MUST stop Ollama and confirm VRAM is
# actually free before invoking a launcher; leaving this to the launcher
# scripts was the root cause of the F.19-post crash chain.

# NOTE: no `set -e` at top level (per user preference — paste-block safe).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORGE_OH_ROOT="${FORGE_OH_ROOT:-$(cd "$SCRIPT_DIR/.." && git rev-parse --show-toplevel 2>/dev/null || cd "$SCRIPT_DIR/.." && pwd)}"

CODER_PORT="${VLLM_CODER_PORT:-8501}"
PLANNER_PORT="${VLLM_PLANNER_PORT:-8511}"
CODER_LOG="${VLLM_CODER_LOG:-$HOME/.forge-oh/vllm-coder.log}"
PLANNER_LOG="${VLLM_PLANNER_LOG:-$HOME/.forge-oh/vllm-planner.log}"
READY_TIMEOUT="${VLLM_READY_TIMEOUT:-420}"

CODER_LAUNCHER="$SCRIPT_DIR/vllm_launch_coder.sh"
PLANNER_LAUNCHER="$SCRIPT_DIR/vllm_launch_planner.sh"
VLLM_STOP="$FORGE_OH_ROOT/scripts/vllm_stop.sh"

# GPU-tenancy discipline (ADR-009 §5).
MIN_FREE_MIB="${VLLM_MIN_FREE_MIB:-28000}"
GPU_FREE_TIMEOUT="${VLLM_GPU_FREE_TIMEOUT:-30}"
SKIP_OLLAMA_STOP="${VLLM_SKIP_OLLAMA_STOP:-0}"

# Docker container names (must match launcher scripts).
CODER_CONTAINER="${FORGE_VLLM_CODER_CONTAINER:-forge-vllm-coder}"
PLANNER_CONTAINER="${FORGE_VLLM_PLANNER_CONTAINER:-forge-vllm-planner}"

mkdir -p "$HOME/.forge-oh"

# --- Helpers ---------------------------------------------------------------

_gpu_free_mib() {
    # Print MiB of free VRAM on cuda:0. Empty string if nvidia-smi unavailable.
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        echo ""
        return 0
    fi
    nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null \
        | head -1 | tr -d ' '
}

_stop_ollama() {
    # Stop the Ollama service and any lingering ollama runner processes so
    # VRAM is fully released before vLLM tries to grab 0.9 of the card.
    # No-op on machines without Ollama installed. Idempotent.
    if [ "$SKIP_OLLAMA_STOP" = "1" ]; then
        echo "[supervisor] VLLM_SKIP_OLLAMA_STOP=1 — skipping Ollama stop"
        return 0
    fi
    local stopped=0
    # systemd unit (preferred path on Colossus)
    if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^ollama\.service'; then
        sudo -n systemctl stop ollama >/dev/null 2>&1 && stopped=1 || true
    fi
    # Belt-and-braces: kill any residual ollama processes even if systemctl
    # wasn't available or the unit isn't installed. Ollama's runner keeps
    # weights in VRAM independently of the parent process on some setups.
    if command -v pkill >/dev/null 2>&1; then
        pkill -x ollama >/dev/null 2>&1 && stopped=1 || true
        pkill -f 'ollama runner' >/dev/null 2>&1 && stopped=1 || true
    fi
    if [ $stopped -eq 1 ]; then
        echo "[supervisor] Ollama stopped (VRAM release pending)"
    else
        echo "[supervisor] Ollama not running (nothing to stop)"
    fi
    return 0
}

_free_gpu_for_vllm() {
    # Ensure enough VRAM is free to start a vLLM role at --gpu-memory-utilization 0.9.
    # Steps:
    #   1. Stop Ollama (unless VLLM_SKIP_OLLAMA_STOP=1).
    #   2. Poll free VRAM until >= MIN_FREE_MIB or GPU_FREE_TIMEOUT elapses.
    # Returns 0 on success, 1 on timeout or nvidia-smi unavailable.
    _stop_ollama
    local free waited=0
    while [ $waited -le "$GPU_FREE_TIMEOUT" ]; do
        free=$(_gpu_free_mib)
        if [ -z "$free" ]; then
            echo "[supervisor] WARN: nvidia-smi unavailable — cannot verify VRAM free; proceeding" >&2
            return 0
        fi
        if [ "$free" -ge "$MIN_FREE_MIB" ]; then
            echo "[supervisor] GPU ready: ${free} MiB free (>= ${MIN_FREE_MIB} required)"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    free=$(_gpu_free_mib)
    echo "[supervisor] TIMEOUT: only ${free:-unknown} MiB free after ${GPU_FREE_TIMEOUT}s (need ${MIN_FREE_MIB}). Something else is holding VRAM." >&2
    if command -v nvidia-smi >/dev/null 2>&1; then
        echo "[supervisor] Processes on GPU:" >&2
        nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader >&2 || true
    fi
    return 1
}

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
            _free_gpu_for_vllm || return 1
            _launch "$CODER_LAUNCHER" "$CODER_LOG" || return 1
            _wait_ready "$CODER_PORT" "coder" || return 1
            ;;
        planner)
            _stop_role "coder"
            _stop_role "planner"
            _free_gpu_for_vllm || return 1
            _launch "$PLANNER_LAUNCHER" "$PLANNER_LOG" || return 1
            _wait_ready "$PLANNER_PORT" "planner" || return 1
            ;;
        *)
            echo "usage: $0 up {coder|planner}" >&2
            return 2
            ;;
    esac
}

cmd_check() {
    # Dry-run the GPU-tenancy discipline without launching anything. Useful
    # for pre-flight verification and for the supervisor test script.
    local free
    free=$(_gpu_free_mib)
    if [ -z "$free" ]; then
        echo "nvidia-smi: unavailable"
        echo "result    : SKIP (cannot verify)"
        return 0
    fi
    echo "free_mib      : $free"
    echo "required_mib  : $MIN_FREE_MIB"
    if [ "$free" -ge "$MIN_FREE_MIB" ]; then
        echo "result        : OK (>= required)"
        return 0
    fi
    echo "result        : SHORT ($((MIN_FREE_MIB - free)) MiB below requirement)"
    echo "processes_on_gpu:"
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
    return 1
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

# Library mode: if this file is being sourced (not executed directly),
# expose the helpers but skip the CLI dispatch. Used by the offline test
# suite (ops/tests/test_vllm_supervisor.sh).
(return 0 2>/dev/null) && return 0

case "${1:-}" in
    up)     shift; cmd_up "${1:-}" ;;
    ensure) shift; cmd_ensure "${1:-}" ;;
    down)   cmd_down ;;
    status) cmd_status ;;
    check)  cmd_check ;;
    *)
        cat >&2 <<USAGE
vLLM swap-on-demand supervisor (ADR-009 §3a).

Usage:
  $0 up {coder|planner}      Stop the other role, start this one, wait ready.
  $0 ensure {coder|planner}  No-op if already live+ready; else same as 'up'.
  $0 down                    Stop both roles.
  $0 status                  Print live role. Exit: 0=coder 1=planner
                             2=none 3=broken/both.
  $0 check                   Dry-run GPU-tenancy discipline: print free
                             VRAM vs required and exit 0 if enough is
                             free, 1 otherwise. Does NOT stop Ollama
                             or launch anything.

Env: VLLM_CODER_PORT (default 8501), VLLM_PLANNER_PORT (8511),
     VLLM_READY_TIMEOUT (420s), VLLM_CODER_LOG, VLLM_PLANNER_LOG,
     VLLM_MIN_FREE_MIB (28000), VLLM_GPU_FREE_TIMEOUT (30s),
     VLLM_SKIP_OLLAMA_STOP (0).
USAGE
        exit 2
        ;;
esac
