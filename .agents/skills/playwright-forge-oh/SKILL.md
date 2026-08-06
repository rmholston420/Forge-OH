---
name: playwright-forge-oh
description: Playwright visual verification discipline for Forge-OH on Colossus. Use whenever writing a new Playwright spec, running e2e tests, taking a screenshot, verifying a UI change, or debugging Playwright failures (HMR handshake, hydration, headless Chromium). Enforces the production-build-only rule, the port :3100 rule, the screenshot commit pattern, and the aria-label discipline.
license: MIT
triggers:
  - playwright
  - "npx playwright"
  - "playwright.config"
  - "tests/e2e/"
  - "PLAYWRIGHT_"
  - "PLAYWRIGHT_FRONTEND_URL"
  - "PLAYWRIGHT_GPU_STRIP_PUSH"
  - "screenshots/"
  - "next start"
  - "next dev"
  - "port 3100"
  - aria-label
  - headless
  - hydration
  - "e2e test"
---

# Forge-OH Playwright Visual Verification

Applies to any Playwright spec, screenshot, or e2e run in the Forge-OH repo. Complements — does not replace — `forge-oh-colossus-ops`.

## Non-Negotiable Rules

1. **Playwright runs against `next start` (port 3100), NEVER `next dev` (port 3000).** HMR websockets break headless Chromium's hydration handshake — the page never becomes interactive.
2. **cwd is `~/dev/forge-oh/src/`, not the repo root.** `playwright.config.ts` lives at `src/playwright.config.ts` and expects `src/` as the working directory.
3. **Env vars are required**: `PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100` and (when the spec pushes screenshots) `PLAYWRIGHT_GPU_STRIP_PUSH=1`.
4. **Screenshots land in `~/dev/forge-oh/screenshots/`, which is gitignored.** Commit via `git add -f` — Playwright specs do this via the auto-push helper.
5. **Selector rule**: prefer `aria-label` over CSS classes or text content. Class names change; aria-labels are semantic and stable.

## Canonical Run Command

```bash
cd ~/dev/forge-oh/src
PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
PLAYWRIGHT_GPU_STRIP_PUSH=1 \
  npx playwright test tests/e2e/<spec>.spec.ts --reporter=list
```

`--reporter=list` gives one-line-per-test output that fits in the terminal. `--reporter=line` or default HTML reports are noisy.

## Full Rebuild + Verify Loop (single paste block)

```bash
cd ~/dev/forge-oh && git pull
fuser -k 3100/tcp 2>/dev/null; sleep 2
npm run build 2>&1 | tail -8
NEXT_PUBLIC_BFF_URL=http://127.0.0.1:8081 \
  nohup npx next start -H 127.0.0.1 -p 3100 >~/.forge-oh/next-prod.log 2>&1 &
sleep 6
curl -s -o /dev/null -w "prod=%{http_code}\n" http://127.0.0.1:3100/runs
cd ~/dev/forge-oh/src
PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
PLAYWRIGHT_GPU_STRIP_PUSH=1 \
  npx playwright test tests/e2e/<spec>.spec.ts --reporter=list
```

## Spec Structure

```typescript
// src/tests/e2e/skills-page.spec.ts
import { test, expect } from "@playwright/test";
import { pushScreenshot } from "./helpers/screenshot-push";

const BASE = process.env.PLAYWRIGHT_FRONTEND_URL ?? "http://127.0.0.1:3100";

test("skills page renders and lists skills", async ({ page }) => {
  await page.goto(`${BASE}/skills`);

  // Wait for the API-driven content — never rely on time-based waits
  await expect(page.getByRole("heading", { name: /skills/i })).toBeVisible();
  await expect(page.locator('[aria-label="Skills table"]')).toBeVisible();

  // At least one skill row
  const rows = page.locator('[aria-label="Skill row"]');
  await expect(rows.first()).toBeVisible();

  // Filter chip interaction
  await page.locator('[aria-label="Filter: user scope"]').click();
  await expect(rows.first()).toBeVisible(); // still at least one after filter

  // Push screenshot
  await page.screenshot({ path: "screenshots/skills-page.png", fullPage: true });
  if (process.env.PLAYWRIGHT_GPU_STRIP_PUSH === "1") {
    await pushScreenshot("screenshots/skills-page.png", "6.6 skills page rendered");
  }
});
```

## Selector Discipline

**Priority order:**

1. `getByRole("button", { name: "..." })` — semantic, screen-reader-aligned
2. `[aria-label="..."]` — explicit accessibility label
3. `getByText("...")` — visible text (fragile if copy changes)
4. `[data-testid="..."]` — last resort, but explicit

**Never use:**
- `.classname` selectors — CSS classes change with refactors
- Deeply nested selectors like `div > div > span.foo > button` — brittle
- Selectors that match `>1` element without `.first()` / `.nth(N)`

### aria-label conventions in Forge-OH

Verified from `GpuStrip` and elsewhere:

- Chip buttons: `Open <metric_key> history` (e.g. `Open temperature_c history`)
- Container aria-label: `GPU health` (data present) or `GPU status` (data missing)
- Filter chips: `Filter: <chip-name>`
- Table containers: `<Domain> table` (e.g., `Skills table`)
- Rows: `<Entity> row` (e.g., `Skill row`)

New pages should follow these naming patterns for consistency.

## Wait Strategies

```typescript
// ✅ Good — wait for the actual thing you care about
await expect(page.getByText("Loading…")).toBeHidden();
await expect(page.locator('[data-testid="skill-row"]').first()).toBeVisible();

// ✅ Good — wait for a network request to complete
await page.waitForResponse(res =>
  res.url().includes("/api/skills") && res.status() === 200
);

// ❌ Bad — arbitrary timeout, flaky
await page.waitForTimeout(2000);

// ❌ Bad — waits for any network idle, brittle in SPAs with polling
await page.waitForLoadState("networkidle");
```

## Common Failure Modes

### HMR websocket handshake fails

Symptom: page loads but stays as an empty skeleton; console shows `WebSocket connection to 'ws://...' failed`.

Cause: running against `next dev` (port 3000). Headless Chromium can't complete the HMR websocket handshake.

Fix: switch to `next start` on port 3100. NEVER debug this by "fixing HMR for headless" — the fix is not to use dev mode.

### Test passes locally, fails in a fresh run

Cause: stale build. `.next/BUILD_ID` is old.

Fix: rebuild before running (`npm run build` from repo root).

### Selector matches multiple elements

```
Error: strict mode violation: locator resolved to 3 elements
```

Fix: add `.first()`, `.nth(N)`, or narrow the selector (`page.locator('[aria-label="..."]').locator('button')`).

### Screenshot is blank / partially rendered

Cause: took the screenshot before hydration completed.

Fix: `await expect(<some-key-element>).toBeVisible()` first, THEN screenshot. Do NOT `waitForTimeout`.

### Screenshot pushed but not visible in the run

Cause: not passing `PLAYWRIGHT_GPU_STRIP_PUSH=1`, or the push helper failed silently.

Fix: check the spec's screenshot-push wrapper. Some specs only push when env is set — this is intentional (local dev shouldn't push).

### `next start` says port already in use

Fix: `fuser -k 3100/tcp 2>/dev/null; sleep 2` before starting. See `forge-oh-colossus-ops` for full port-kill discipline.

## Debugging a Failing Test

1. Search DEBUG_LOG.md first (mandatory per project instructions)
2. Re-run with `--headed --debug` to step through in a real browser:
   ```bash
   PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
     npx playwright test tests/e2e/<spec>.spec.ts --headed --debug
   ```
3. Check the trace file if generated: `npx playwright show-trace trace.zip`
4. Read the browser console output (Playwright logs it)
5. Compare visual snapshot against the last known-good screenshot
6. Log the finding to DEBUG_LOG.md before fixing

## Committing Screenshots

Screenshots are gitignored globally but committed per-spec:

```bash
# In the spec, after page.screenshot(...):
git add -f screenshots/<file>.png
git commit -m "6.6: skills page screenshot"
git push origin main
```

The push helper (`src/tests/e2e/helpers/screenshot-push.ts`) does this automatically when `PLAYWRIGHT_GPU_STRIP_PUSH=1` is set. Verify it succeeded — the auto-push commit shows up as `Perplexity Computer <computer@perplexity.ai>` in git log.

## Anti-Patterns

- ❌ Playwright against `next dev` / port 3000 (HMR handshake breaks)
- ❌ Running Playwright from repo root (config expects `src/`)
- ❌ Class-based selectors (change with refactors)
- ❌ `waitForTimeout(ms)` for arbitrary waits (flaky)
- ❌ `waitForLoadState("networkidle")` in an SPA with polling (never idles)
- ❌ Skipping the DEBUG_LOG lookup before debugging a failing test
- ❌ Committing screenshots via a manual `git add -f` when the auto-push helper exists
- ❌ Screenshots without a descriptive commit message
- ❌ Specs that don't restore state (leave data around for next run)
- ❌ Multiple specs writing to the same screenshot filename (last-write-wins collision)

## Cross-References

- `forge-oh-colossus-ops` — port/paths/restart recipes
- `forge-oh-debug-driver` — DEBUG_LOG search protocol
- `web-frontend-authoring` (user scope) — component patterns
- `bff-fe-contract-sync` — verifying data flows end-to-end

## Checklist for a New Spec

1. File at `src/tests/e2e/<name>.spec.ts`
2. Uses `PLAYWRIGHT_FRONTEND_URL` env var (default `http://127.0.0.1:3100`)
3. Selectors are role/aria-based, not class-based
4. `page.goto` followed by explicit `expect(...).toBeVisible()` for the key element
5. Wait strategy is content-based, not time-based
6. Screenshot at the end with a descriptive filename
7. `pushScreenshot` invoked when `PLAYWRIGHT_GPU_STRIP_PUSH=1`
8. Test passes 3 times in a row (no flakes)
9. Test cleanup — no leftover data or open connections
10. BUILD_LOG updated after spec lands
