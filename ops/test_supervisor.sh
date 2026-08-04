#!/usr/bin/env bash
# Offline tests for ops/vllm_supervisor.sh GPU-tenancy discipline.
#
# Uses PATH-injected stubs to fake `nvidia-smi`, `systemctl`, `pkill`,
# `sudo`, `docker`, `curl`, and `fuser` so we can exercise the supervisor
# helpers without touching the real system.
#
# Runs the supervisor's helper functions by sourcing it in "library mode":
# we set `SUPERVISOR_TEST_MODE=1` and short-circuit the dispatch by passing
# an unknown command through a sub-shell. In practice we `bash -c 'source
# ops/vllm_supervisor.sh; <fn>'` after stubs are on PATH.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SUPERVISOR="$REPO_ROOT/ops/vllm_supervisor.sh"

PASS=0
FAIL=0
FAILURES=()

# --- test harness ----------------------------------------------------------

_setup_stub_dir() {
    # Print a fresh temp dir with executable stubs prepended to PATH.
    local dir
    dir=$(mktemp -d)
    echo "$dir"
}

_stub_nvidia_smi_free() {
    # Args: DIR MIB. Create nvidia-smi stub returning MIB free.
    local dir="$1" mib="$2"
    cat > "$dir/nvidia-smi" <<STUB
#!/usr/bin/env bash
# Fake nvidia-smi returning fixed free MiB.
if [[ "\$*" == *"--query-gpu=memory.free"* ]]; then
    echo "$mib"
    exit 0
fi
if [[ "\$*" == *"--query-compute-apps"* ]]; then
    echo "1234, fake-ollama-runner, 22000 MiB"
    exit 0
fi
exit 0
STUB
    chmod +x "$dir/nvidia-smi"
}

_stub_dynamic_nvidia_smi() {
    # Args: DIR START_MIB END_MIB THRESHOLD_CALL.
    # nvidia-smi returns START until the THRESHOLD_CALL'th invocation, then END.
    # Simulates VRAM release after Ollama stop completes.
    local dir="$1" start="$2" end="$3" threshold="$4"
    cat > "$dir/nvidia-smi" <<STUB
#!/usr/bin/env bash
STATE="\${TMPDIR:-/tmp}/nvsmi_call_count.\$\$"
STATE_DIR="$dir"
COUNTER="\$STATE_DIR/.nvsmi_calls"
touch "\$COUNTER"
CALLS=\$(wc -l < "\$COUNTER" | tr -d ' ')
CALLS=\$((CALLS + 1))
echo "call" >> "\$COUNTER"
if [[ "\$*" == *"--query-gpu=memory.free"* ]]; then
    if [ \$CALLS -lt $threshold ]; then
        echo "$start"
    else
        echo "$end"
    fi
    exit 0
fi
if [[ "\$*" == *"--query-compute-apps"* ]]; then
    echo "1234, fake-runner, ${start} MiB"
    exit 0
fi
exit 0
STUB
    chmod +x "$dir/nvidia-smi"
}

_stub_systemctl() {
    # Args: DIR HAS_SYS_OLLAMA_UNIT (0|1) [HAS_USER_OLLAMA_UNIT (0|1)]. Create
    # systemctl stub that also tracks --user vs system scope.
    #
    # HAS_USER_OLLAMA_UNIT defaults to 0 (backwards compat with existing tests).
    local dir="$1" has_sys="$2" has_user="${3:-0}"
    cat > "$dir/systemctl" <<STUB
#!/usr/bin/env bash
# Detect --user flag (may appear before the subcommand)
SCOPE=system
if [ "\$1" = "--user" ]; then
    SCOPE=user
    shift
fi
if [ "\$1" = "list-unit-files" ]; then
    if [ "\$SCOPE" = "system" ] && [ "$has_sys" = "1" ]; then
        echo "ollama.service enabled enabled"
    fi
    if [ "\$SCOPE" = "user" ] && [ "$has_user" = "1" ]; then
        echo "ollama.service enabled enabled"
    fi
    exit 0
fi
if [ "\$1" = "stop" ] && [ "\$2" = "ollama" ]; then
    if [ "\$SCOPE" = "system" ]; then
        echo "STUB_SYSTEMCTL_STOP_CALLED" >> "$dir/.calls"
    else
        echo "STUB_SYSTEMCTL_USER_STOP_CALLED" >> "$dir/.calls"
    fi
    exit 0
fi
exit 0
STUB
    chmod +x "$dir/systemctl"
}

_stub_sudo() {
    # Args: DIR. Create sudo stub that just execs its args.
    local dir="$1"
    cat > "$dir/sudo" <<'STUB'
#!/usr/bin/env bash
# Skip -n / other flags then exec.
while [ "${1:-}" = "-n" ] || [ "${1:-}" = "-E" ]; do shift; done
exec "$@"
STUB
    chmod +x "$dir/sudo"
}

_stub_pkill() {
    # Args: DIR. pkill stub logs invocation and returns 1 (nothing to kill).
    local dir="$1"
    cat > "$dir/pkill" <<STUB
#!/usr/bin/env bash
echo "STUB_PKILL \$*" >> "$dir/.calls"
exit 1
STUB
    chmod +x "$dir/pkill"
}

_stub_docker() {
    # Args: DIR. docker stub does nothing (no containers to remove).
    local dir="$1"
    cat > "$dir/docker" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
    chmod +x "$dir/docker"
}

_stub_fuser() {
    local dir="$1"
    cat > "$dir/fuser" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
    chmod +x "$dir/fuser"
}

_stub_ss() {
    # Args: DIR [LISTENING (0|1)]. Default: not listening on :11434.
    # When LISTENING=1, ss -lntp prints a line matching ':11434 '.
    local dir="$1" listening="${2:-0}"
    cat > "$dir/ss" <<STUB
#!/usr/bin/env bash
if [ "$listening" = "1" ]; then
    echo 'LISTEN 0      4096       127.0.0.1:11434      0.0.0.0:*    users:(("ollama",pid=999,fd=4))'
fi
exit 0
STUB
    chmod +x "$dir/ss"
}

_stub_curl() {
    # Args: DIR. curl stub always fails (nothing listening).
    local dir="$1"
    cat > "$dir/curl" <<'STUB'
#!/usr/bin/env bash
exit 22
STUB
    chmod +x "$dir/curl"
}

_full_stub_dir() {
    # One-stop stub environment: everything the supervisor might invoke.
    local dir="$1"
    _stub_systemctl "$dir" 1
    _stub_sudo "$dir"
    _stub_pkill "$dir"
    _stub_docker "$dir"
    _stub_fuser "$dir"
    _stub_ss "$dir"
    _stub_curl "$dir"
}

_run_super_fn() {
    # Args: STUB_DIR FN [ARGS...]. Sources supervisor with stubs on PATH,
    # then runs FN. PATH keeps original entries so bash/coreutils remain available.
    local dir="$1"; shift
    local fn="$1"; shift
    local args="$*"
    PATH="$dir:$PATH" bash -c "
        source '$SUPERVISOR' 2>/dev/null || true
        $fn $args
    "
}

_check() {
    # Args: NAME CONDITION [MESSAGE_ON_FAIL].
    local name="$1" cond="$2" msg="${3:-}"
    if eval "$cond"; then
        echo "  PASS: $name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $name — $msg"
        FAIL=$((FAIL + 1))
        FAILURES+=("$name")
    fi
}

# --- tests -----------------------------------------------------------------

test_gpu_free_mib_reports_value() {
    echo "test_gpu_free_mib_reports_value"
    local dir out
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 30000
    out=$(_run_super_fn "$dir" "_gpu_free_mib")
    _check "returns 30000" "[ '$out' = '30000' ]" "got '$out'"
    rm -rf "$dir"
}

test_gpu_free_mib_missing_nvidia_smi() {
    echo "test_gpu_free_mib_missing_nvidia_smi"
    local dir out
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    # No nvidia-smi stub. To simulate "nvidia-smi not on PATH" without
    # breaking bash/coreutils, put a wrapper `nvidia-smi` that exec's a
    # non-existent binary so `command -v` still finds it — but that
    # defeats the point. Instead we shim `command` inside the sub-shell
    # to report nvidia-smi as absent.
    out=$(PATH="$dir:$PATH" bash -c "
        source '$SUPERVISOR' 2>/dev/null
        command() {
            if [ \"\$1\" = '-v' ] && [ \"\$2\" = 'nvidia-smi' ]; then return 1; fi
            builtin command \"\$@\"
        }
        _gpu_free_mib
    ")
    _check "returns empty string" "[ -z '$out' ]" "got '$out'"
    rm -rf "$dir"
}

test_free_gpu_succeeds_when_immediately_free() {
    echo "test_free_gpu_succeeds_when_immediately_free"
    local dir rc
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 31000  # already above default 28000
    PATH="$dir:$PATH" bash -c "source '$SUPERVISOR' 2>/dev/null; _free_gpu_for_vllm" >/dev/null 2>&1
    rc=$?
    _check "exit 0 when GPU already free" "[ $rc -eq 0 ]" "got rc=$rc"
    rm -rf "$dir"
}

test_free_gpu_fails_on_timeout() {
    echo "test_free_gpu_fails_on_timeout"
    local dir rc
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 10000  # far below 28000
    PATH="$dir:$PATH" VLLM_GPU_FREE_TIMEOUT=4 bash -c "source '$SUPERVISOR' 2>/dev/null; _free_gpu_for_vllm" >/dev/null 2>&1
    rc=$?
    _check "exit 1 on VRAM-short timeout" "[ $rc -eq 1 ]" "got rc=$rc"
    rm -rf "$dir"
}

test_free_gpu_waits_then_succeeds() {
    echo "test_free_gpu_waits_then_succeeds"
    local dir rc
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    # 3 calls at 10000, then 30000 on call 4+ (simulates VRAM release after
    # Ollama stop is honored).
    _stub_dynamic_nvidia_smi "$dir" 10000 30000 3
    PATH="$dir:$PATH" VLLM_GPU_FREE_TIMEOUT=20 bash -c "source '$SUPERVISOR' 2>/dev/null; _free_gpu_for_vllm" >/dev/null 2>&1
    rc=$?
    _check "exit 0 after waiting for VRAM to free" "[ $rc -eq 0 ]" "got rc=$rc"
    rm -rf "$dir"
}

test_free_gpu_skips_ollama_when_env_set() {
    echo "test_free_gpu_skips_ollama_when_env_set"
    local dir out
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 30000
    out=$(PATH="$dir:$PATH" VLLM_SKIP_OLLAMA_STOP=1 bash -c "source '$SUPERVISOR' 2>/dev/null; _free_gpu_for_vllm" 2>&1)
    _check "prints skip message" "echo '$out' | grep -q 'skipping Ollama stop'" "output: $out"
    _check "systemctl not invoked" "[ ! -f '$dir/.calls' ] || ! grep -q STUB_SYSTEMCTL_STOP_CALLED '$dir/.calls'" \
        "calls file: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    rm -rf "$dir"
}

test_stop_ollama_calls_systemctl_when_unit_exists() {
    echo "test_stop_ollama_calls_systemctl_when_unit_exists"
    local dir
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    PATH="$dir:$PATH" bash -c "source '$SUPERVISOR' 2>/dev/null; _stop_ollama" >/dev/null 2>&1
    _check "systemctl stop ollama was invoked" \
        "grep -q STUB_SYSTEMCTL_STOP_CALLED '$dir/.calls'" \
        "calls: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    _check "pkill ollama attempted" "grep -q 'STUB_PKILL' '$dir/.calls'" \
        "calls: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    rm -rf "$dir"
}

test_stop_ollama_no_op_when_unit_absent() {
    echo "test_stop_ollama_no_op_when_unit_absent"
    local dir out
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_systemctl "$dir" 0 0  # override: no ollama unit in either scope
    out=$(PATH="$dir:$PATH" bash -c "source '$SUPERVISOR' 2>/dev/null; _stop_ollama" 2>&1)
    _check "prints 'not running' when unit absent + pkill finds nothing" \
        "echo '$out' | grep -q 'not running'" "output: $out"
    rm -rf "$dir"
}

test_stop_ollama_stops_user_scope_unit() {
    # Regression guard for DEBUG_LOG 2026-08-04 02:42 EDT: on Colossus,
    # Ollama was running as a user-scope systemd unit while the system-scope
    # unit reported inactive. The pre-fix supervisor only stopped the system
    # scope, missing the user-scope Ollama entirely.
    echo "test_stop_ollama_stops_user_scope_unit"
    local dir
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_systemctl "$dir" 0 1  # override: no system unit, but user unit exists
    PATH="$dir:$PATH" bash -c "source '$SUPERVISOR' 2>/dev/null; _stop_ollama" >/dev/null 2>&1
    _check "user-scope systemctl stop was invoked" \
        "grep -q STUB_SYSTEMCTL_USER_STOP_CALLED '$dir/.calls'" \
        "calls: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    _check "system-scope systemctl stop was NOT invoked (no system unit)" \
        "! grep -q STUB_SYSTEMCTL_STOP_CALLED '$dir/.calls'" \
        "calls: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    rm -rf "$dir"
}

test_stop_ollama_stops_both_scopes_when_both_present() {
    echo "test_stop_ollama_stops_both_scopes_when_both_present"
    local dir
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_systemctl "$dir" 1 1  # both scopes have the unit
    PATH="$dir:$PATH" bash -c "source '$SUPERVISOR' 2>/dev/null; _stop_ollama" >/dev/null 2>&1
    _check "system-scope systemctl stop was invoked" \
        "grep -q STUB_SYSTEMCTL_STOP_CALLED '$dir/.calls'" \
        "calls: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    _check "user-scope systemctl stop was invoked" \
        "grep -q STUB_SYSTEMCTL_USER_STOP_CALLED '$dir/.calls'" \
        "calls: $(cat "$dir/.calls" 2>/dev/null || echo none)"
    rm -rf "$dir"
}

test_cmd_check_flags_ollama_listener_when_present() {
    # DEBUG_LOG 2026-08-04 02:42 EDT: cmd_check must surface the presence of
    # an Ollama listener on :11434 even when the system-scope unit is
    # inactive, because the listener may belong to a user-scope Ollama.
    echo "test_cmd_check_flags_ollama_listener_when_present"
    local dir out
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 30000  # plenty of VRAM — result=OK
    _stub_ss "$dir" 1                    # override: :11434 is listening
    out=$(PATH="$dir:$PATH" bash "$SUPERVISOR" check 2>&1)
    _check "cmd_check reports ollama_listener PRESENT" \
        "echo '$out' | grep -q 'ollama_listener: PRESENT'" \
        "output: $out"
    _check "cmd_check still reports OK when VRAM sufficient" \
        "echo '$out' | grep -q 'result        : OK'" \
        "output: $out"
    rm -rf "$dir"
}

test_cmd_check_reports_ollama_listener_absent() {
    echo "test_cmd_check_reports_ollama_listener_absent"
    local dir out
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 30000
    _stub_ss "$dir" 0  # default: not listening
    out=$(PATH="$dir:$PATH" bash "$SUPERVISOR" check 2>&1)
    _check "cmd_check reports ollama_listener absent" \
        "echo '$out' | grep -q 'ollama_listener: absent'" \
        "output: $out"
    rm -rf "$dir"
}

test_cmd_check_reports_short() {
    echo "test_cmd_check_reports_short"
    local dir out rc
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 15000
    out=$(PATH="$dir:$PATH" bash "$SUPERVISOR" check 2>&1)
    rc=$?
    _check "cmd_check exits 1 on short" "[ $rc -eq 1 ]" "rc=$rc"
    _check "cmd_check prints SHORT" "echo '$out' | grep -q 'SHORT'" "output: $out"
    rm -rf "$dir"
}

test_cmd_check_reports_ok() {
    echo "test_cmd_check_reports_ok"
    local dir out rc
    dir=$(_setup_stub_dir)
    _full_stub_dir "$dir"
    _stub_nvidia_smi_free "$dir" 31000
    out=$(PATH="$dir:$PATH" bash "$SUPERVISOR" check 2>&1)
    rc=$?
    _check "cmd_check exits 0 on OK" "[ $rc -eq 0 ]" "rc=$rc"
    _check "cmd_check prints OK" "echo '$out' | grep -q 'OK'" "output: $out"
    rm -rf "$dir"
}

# --- run -------------------------------------------------------------------

echo "vLLM supervisor offline tests"
echo "supervisor: $SUPERVISOR"
echo "----"

test_gpu_free_mib_reports_value
test_gpu_free_mib_missing_nvidia_smi
test_free_gpu_succeeds_when_immediately_free
test_free_gpu_fails_on_timeout
test_free_gpu_waits_then_succeeds
test_free_gpu_skips_ollama_when_env_set
test_stop_ollama_calls_systemctl_when_unit_exists
test_stop_ollama_no_op_when_unit_absent
test_stop_ollama_stops_user_scope_unit
test_stop_ollama_stops_both_scopes_when_both_present
test_cmd_check_reports_short
test_cmd_check_reports_ok
test_cmd_check_flags_ollama_listener_when_present
test_cmd_check_reports_ollama_listener_absent

echo "----"
echo "PASS: $PASS  FAIL: $FAIL"
if [ $FAIL -gt 0 ]; then
    echo "failures:"
    for f in "${FAILURES[@]}"; do echo "  - $f"; done
    exit 1
fi
exit 0
