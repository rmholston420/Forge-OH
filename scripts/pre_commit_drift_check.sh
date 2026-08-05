#!/usr/bin/env bash
# scripts/pre_commit_drift_check.sh — enforce ADR-016 Colossus<->GitHub parity
#
# Blocks commits when files exist on disk that are neither tracked nor
# explicitly ignored. This catches silent drift at commit time.
#
# Overridable with `git commit --no-verify` for legitimate WIP where you
# know drift exists and will resolve it in a follow-up commit.
#
# Exit codes:
#   0 = no drift, commit proceeds
#   1 = drift detected, commit blocked
#
# Called from .pre-commit-config.yaml.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRIFT=$(git ls-files --others --exclude-standard)

if [ -z "$DRIFT" ]; then
  # No drift — commit may proceed.
  exit 0
fi

echo "" >&2
echo "====================================================================" >&2
echo "  ADR-016 VIOLATION: Colossus<->GitHub mirror drift detected" >&2
echo "====================================================================" >&2
echo "" >&2
echo "The following files exist on Colossus but are neither tracked in git" >&2
echo "nor explicitly ignored by .gitignore:" >&2
echo "" >&2
echo "$DRIFT" | sed 's/^/  /' >&2
echo "" >&2
echo "Per ADR-016, every path must be either tracked or explicitly ignored." >&2
echo "" >&2
echo "Options:" >&2
echo "  1. Track the file(s):  git add <path>" >&2
echo "  2. Ignore with rationale: add a rule + comment to .gitignore" >&2
echo "  3. Delete the file(s) if they're scratch: rm <path>" >&2
echo "  4. Override this check (WIP): git commit --no-verify" >&2
echo "" >&2
echo "====================================================================" >&2
exit 1
