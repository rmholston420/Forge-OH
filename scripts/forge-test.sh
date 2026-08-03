#!/usr/bin/env bash
# forge-test.sh — full quality gate: lint + type + test + coverage + e2e
#
# Runs (in order):
#   1. ruff check         (bff/)
#   2. ruff format --check (bff/)
#   3. mypy               (bff/)
#   4. pytest + coverage  (bff/tests/)
#   5. tsc --noEmit
#   6. eslint             (pnpm lint)
#   7. vitest + coverage
#   8. playwright e2e     (requires BFF running — use scripts/forge-up.sh)
#
# Env overrides:
#   SKIP_E2E=1      skip playwright
#   SKIP_COVERAGE=1 skip both coverage reports (faster)
#   STRICT_LINT=1   use pnpm lint:strict (zero warnings)
#
# Exit code: 0 if every step passes, 1 otherwise. Each step's status is
# summarised at the end regardless.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f ".oh-venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .oh-venv/bin/activate
fi

# Colours
C_HDR='\033[1;35m'; C_OK='\033[32m'; C_FAIL='\033[31m'; C_INFO='\033[36m'; C_END='\033[0m'
hdr()  { printf "\n${C_HDR}══ %s ══${C_END}\n" "$*"; }
info() { printf "${C_INFO}%s${C_END}\n" "$*"; }
ok()   { printf "${C_OK}✅ %s${C_END}\n" "$*"; }
fail() { printf "${C_FAIL}❌ %s${C_END}\n" "$*"; }

# Track results
declare -A RESULT

run_step() {
  local key="$1" name="$2"; shift 2
  hdr "$name"
  if "$@"; then
    RESULT[$key]="pass"
    ok "$name"
  else
    RESULT[$key]="fail"
    fail "$name"
  fi
}

# 1. ruff lint
run_step ruff_lint "ruff check bff/" \
  ruff check bff/

# 2. ruff format check
run_step ruff_fmt "ruff format --check bff/" \
  ruff format --check bff/

# 3. mypy
run_step mypy "mypy bff/" \
  bash -c 'mypy bff/'

# 4. pytest (with or without coverage)
if [ "${SKIP_COVERAGE:-0}" = "1" ]; then
  run_step pytest "pytest bff/tests/" \
    python -m pytest bff/tests/ -q
else
  run_step pytest "pytest bff/tests/ + coverage" \
    python -m pytest bff/tests/ --cov=bff --cov-report=term --cov-report=html:.cov-html-bff -q
fi

# 5. tsc
run_step tsc "tsc --noEmit" \
  pnpm exec tsc --noEmit

# 6. eslint
LINT_CMD="lint"
[ "${STRICT_LINT:-0}" = "1" ] && LINT_CMD="lint:strict"
run_step eslint "pnpm $LINT_CMD" \
  pnpm "$LINT_CMD"

# 7. vitest
if [ "${SKIP_COVERAGE:-0}" = "1" ]; then
  run_step vitest "vitest run" \
    pnpm exec vitest run
else
  run_step vitest "vitest run --coverage" \
    pnpm exec vitest run --coverage
fi

# 8. playwright (needs live BFF)
if [ "${SKIP_E2E:-0}" = "1" ]; then
  info "SKIP_E2E=1 — skipping playwright"
  RESULT[e2e]="skipped"
else
  # Warn if BFF is not up.
  if ! ss -ltn "sport = :8081" 2>/dev/null | tail -n +2 | grep -q ':'; then
    fail "BFF not listening on :8081 — run scripts/forge-up.sh first"
    RESULT[e2e]="skipped-no-bff"
  else
    run_step e2e "playwright e2e (real BFF)" \
      pnpm test:e2e:real
  fi
fi

# ---- Summary -------------------------------------------------------------
hdr "SUMMARY"
declare -a ORDER=(ruff_lint ruff_fmt mypy pytest tsc eslint vitest e2e)
declare -A LABELS=(
  [ruff_lint]="ruff check"
  [ruff_fmt]="ruff format --check"
  [mypy]="mypy"
  [pytest]="pytest + backend coverage"
  [tsc]="tsc --noEmit"
  [eslint]="eslint (pnpm ${LINT_CMD})"
  [vitest]="vitest + frontend coverage"
  [e2e]="playwright e2e"
)
failed=0
for k in "${ORDER[@]}"; do
  status="${RESULT[$k]:-not-run}"
  case "$status" in
    pass)             printf "  ${C_OK}PASS${C_END}   %s\n" "${LABELS[$k]}" ;;
    fail)             printf "  ${C_FAIL}FAIL${C_END}   %s\n" "${LABELS[$k]}"; failed=1 ;;
    skipped|skipped-no-bff) printf "  SKIP   %s (${status})\n" "${LABELS[$k]}" ;;
    *)                printf "  ????   %s (${status})\n" "${LABELS[$k]}" ;;
  esac
done

if [ "$failed" -eq 0 ]; then
  printf "\n${C_OK}✅ ALL GREEN${C_END}\n"
  exit 0
else
  printf "\n${C_FAIL}❌ ONE OR MORE STEPS FAILED${C_END}\n"
  exit 1
fi
