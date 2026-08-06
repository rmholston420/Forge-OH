---
name: shell-hygiene
description: Bash scripting and paste-block discipline. Use when writing a shell script, emitting a multi-line paste block for a user's interactive shell, running long-running processes, or piping across processes. Prevents the most common failure modes — set -e killing an interactive shell, silent pipe failures, unquoted expansions, and unreaped background processes.
license: MIT
triggers:
  - bash
  - shell script
  - set -e
  - set -euo pipefail
  - "#!/bin/bash"
  - heredoc
  - subshell
  - background process
  - nohup
  - trap
  - pipefail
---

# Shell Hygiene

## The Paste-Block Rule — Never Kill the User's Shell

If you emit a multi-line command block for the user to paste into their interactive bash:

**Never start with `set -e` or `set -euo pipefail` at the top level.**

Reason: any command that returns non-zero — a `docker rm -f` on a nonexistent container, a `curl` to a not-yet-ready endpoint, a `pkill` that finds no process — will exit the login shell, closing their terminal or logging them out.

Two safe patterns:

```bash
# ✅ Wrap the whole paste in a subshell — errors abort the subshell only
( set -e
  cd ~/project
  docker rm -f old-container
  curl -sf http://localhost:8080/health
)

# ✅ Or use || true / && conjunctions and skip set -e entirely
cd ~/project
docker rm -f old-container 2>/dev/null || true
sleep 3
curl -sf http://localhost:8080/health || echo "not ready yet"
```

Inside a script file (`#!/usr/bin/env bash` at the top), `set -euo pipefail` is fine and encouraged — the script has its own process.

## The pipefail Rule

`set -euo pipefail` catches:
- `-e` → exit on unhandled non-zero
- `-u` → unset variables are errors
- `-o pipefail` → pipeline exit status is the rightmost non-zero, not just the last command's

Without `pipefail`:

```bash
some_command_that_fails | grep -q "pattern"
# Exit status is grep's — 0 if pattern found, 1 if not.
# The upstream failure is invisible.
```

With `pipefail`, the upstream failure propagates. Use it in every script.

## Quote Every Variable Expansion

```bash
# ❌ Word-splits on spaces, glob-expands on * or ?
rm -rf $path/tmp
if [ $status = ok ]; then ...

# ✅ Safe
rm -rf "$path/tmp"
if [ "$status" = "ok" ]; then ...
```

Exception: intentional word-splitting for arrays. Use arrays for that:

```bash
args=(--flag1 --flag2 "with a space")
some_command "${args[@]}"
```

## Heredocs — The Right Delimiter

```bash
# ✅ Literal — no variable expansion, no command substitution
cat > file.txt <<'EOF'
$var stays literal
$(command) stays literal
EOF

# ✅ Expanded — variables and commands substituted
cat > file.txt <<EOF
$var expands
$(command) runs
EOF
```

Almost always use `<<'EOF'` (single-quoted). Only use unquoted when you specifically need substitution — and then never inside a paste block for the user's shell (double whammy of set -e + accidental expansion).

## Background Processes

```bash
# ❌ Bare & — you lose the PID and can't wait or kill cleanly
long_running_command &

# ✅ Capture PID, redirect logs
nohup long_running_command >/tmp/mycmd.log 2>&1 &
echo $! > /tmp/mycmd.pid

# ✅ Kill by pidfile later
kill "$(cat /tmp/mycmd.pid)" 2>/dev/null || true
```

If you need to wait for a service to be ready before proceeding, poll — don't `sleep 30`:

```bash
for i in $(seq 1 60); do
  curl -sf http://localhost:8080/health >/dev/null && { echo "ready"; break; }
  sleep 1
done
```

## Cleanup — trap EXIT

Scripts that create temp files or background processes should clean up on exit:

```bash
#!/usr/bin/env bash
set -euo pipefail

tmpdir=$(mktemp -d)
bg_pid=""

cleanup() {
  [[ -n "$bg_pid" ]] && kill "$bg_pid" 2>/dev/null || true
  rm -rf "$tmpdir"
}
trap cleanup EXIT

# ... work ...
some_long_command &
bg_pid=$!

# When the script exits (success or failure), cleanup runs.
```

## Command Substitution

```bash
# ❌ Backticks — nesting is painful, quoting is ambiguous
result=`some_command`

# ✅ $()
result=$(some_command)
result=$(some_command --with "quoted args" | filter)
```

## Common Anti-Patterns

- ❌ `cd $dir && do_thing` — if `cd` fails, `do_thing` doesn't run, but the script continues. Use `set -e` or `cd "$dir" || exit`.
- ❌ `[ $var == "x" ]` — `==` is bash-only; use `=` for POSIX. And quote `$var`.
- ❌ `ls | grep pattern` — parse `find` output instead: `find . -name '*pattern*'` or use globs
- ❌ `for f in $(ls *.txt)` — breaks on filenames with spaces. Use `for f in *.txt`.
- ❌ `some_command 2>&1 >file` — order matters! This sends stderr to the terminal and stdout to file. Correct is `some_command >file 2>&1`.
- ❌ `eval $user_input` — code injection. Never eval untrusted input.
- ❌ Missing `--` before user-supplied args: `rm -- "$file"` protects against filenames starting with `-`.

## Emitting Paste Blocks for a User's Shell — Checklist

1. No top-level `set -e` / `set -euo pipefail` (wrap in `( ... )` if you need it)
2. Every `$var` is `"$var"`
3. `|| true` on commands that legitimately might not-exit-zero (kill, rm -f nonexistent)
4. Heredocs use `<<'EOF'` unless expansion is required
5. Long-running processes go to background with pidfile + log redirect
6. Health-check by polling `curl -sf`, not `sleep`
