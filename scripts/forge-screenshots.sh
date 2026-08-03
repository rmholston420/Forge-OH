#!/usr/bin/env bash
# forge-screenshots.sh — capture full-page Playwright screenshots of every
# route + modal + run-detail tab, then commit them to a throwaway branch
# so the agent can read the PNGs by pulling that branch into its mirror.
#
# Usage:  bash scripts/forge-screenshots.sh
#
# Result:
#   - screenshots/*.png in the working tree
#   - branch: agent/screenshots-YYYYMMDD-HHMMSS  (pushed with --force-with-lease)
#   - the branch name is printed so you can hand it back to me.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

BRANCH="agent/screenshots-$(date +%Y%m%d-%H%M%S)"

echo "── Ensuring services are current (forge-up will restart BFF) ──"
bash "$REPO_ROOT/scripts/forge-up.sh"

echo "── Cleaning old screenshots ──"
rm -rf screenshots
mkdir -p screenshots

echo "── Running visual-tour spec ──"
pnpm exec playwright test src/tests/e2e/visual-tour.spec.ts --reporter=list

echo "── Committing PNGs to $BRANCH ──"
git checkout -B "$BRANCH"
git add -f screenshots/
git -c user.name="Perplexity Computer" -c user.email="computer@perplexity.ai" \
  commit -m "chore(screenshots): visual tour capture $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push --force-with-lease origin "$BRANCH"

echo
echo "══════════════════════════════════════════════════════════════"
echo " ✅ Screenshots pushed to branch:"
echo "     $BRANCH"
echo " Paste this branch name back to the agent."
echo "══════════════════════════════════════════════════════════════"

# Return to main so we don't leave the working tree on the screenshots branch.
git checkout main
