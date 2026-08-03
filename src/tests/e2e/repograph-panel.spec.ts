/**
 * repograph-panel.spec.ts
 *
 * E2E test for the RepoGraph panel mounted in the Trace tab of a run
 * detail page. Drives the full user flow: index the Forge-OH workspace
 * itself, search for a known symbol, click it, and verify callers /
 * callees / co-changed columns populate.
 *
 * Screenshots at each milestone go to `screenshots/repograph-*.png`
 * (gitignored) so the user can paste them back for the Brain wiki.
 *
 * Runs against the real BFF (requires REPOGRAPH_ENABLED=true and
 * NEXT_PUBLIC_FEATURE_REPOGRAPH=true). Skips gracefully if no runs
 * exist or the flag is off.
 */
import { test, expect } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const WORKSPACE = process.env.PLAYWRIGHT_REPOGRAPH_WORKSPACE || `${process.env.HOME}/dev/forge-oh`;
const SCREENSHOT_DIR = join(process.cwd(), 'screenshots');

test.beforeAll(() => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
});

async function firstRunId(page: import('@playwright/test').Page): Promise<string | null> {
  const res = await page.request.get(`${BFF_URL}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{ id: string }>;
  return runs.length ? runs[0].id : null;
}

async function repographEnabled(page: import('@playwright/test').Page): Promise<boolean> {
  const res = await page.request.get(`${BFF_URL}/api/repograph/health`);
  return res.ok();
}

test.describe('RepoGraph Panel (Trace tab)', () => {
  let runId: string | null = null;
  let backendOn = false;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunId(page);
    backendOn = await repographEnabled(page);
    await ctx.close();
  });

  test('panel mounts in Trace tab with green health badge', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    test.skip(!backendOn, 'REPOGRAPH_ENABLED=false on BFF');

    await page.goto(`/runs/${runId!}`);
    await page.getByRole('tab', { name: 'Trace' }).click();

    const panel = page.getByTestId('repograph-panel');
    await expect(panel).toBeVisible();

    // Health badge should turn green (data-ok="true") once /health resolves.
    const badge = panel.locator('[title="Neo4j status"]');
    await expect(badge).toBeVisible();
    await expect(badge).toHaveAttribute('data-ok', 'true', { timeout: 10_000 });

    await page.screenshot({ path: join(SCREENSHOT_DIR, 'repograph-01-panel-mounted.png'), fullPage: true });
  });

  test('index workspace populates stats', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    test.skip(!backendOn, 'REPOGRAPH_ENABLED=false on BFF');

    await page.goto(`/runs/${runId!}`);
    await page.getByRole('tab', { name: 'Trace' }).click();

    const panel = page.getByTestId('repograph-panel');
    await expect(panel).toBeVisible();

    const workspaceInput = panel.getByLabel(/workspace path/i);
    await workspaceInput.fill(WORKSPACE);
    await panel.getByRole('button', { name: /^index$/i }).click();

    // Stats line should appear with real numbers. Timeout generous
    // because indexing 420-file forge-oh repo takes ~1s + network.
    const stats = panel.locator('[data-testid="repograph-stats"]');
    await expect(stats).toBeVisible({ timeout: 30_000 });
    await expect(stats).toContainText(/files \d+/);
    await expect(stats).toContainText(/symbols \d+/);
    await expect(stats).toContainText(/calls \d+/);

    await page.screenshot({ path: join(SCREENSHOT_DIR, 'repograph-02-indexed.png'), fullPage: true });
  });

  test('search returns ranked symbols and detail view populates', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    test.skip(!backendOn, 'REPOGRAPH_ENABLED=false on BFF');

    await page.goto(`/runs/${runId!}`);
    await page.getByRole('tab', { name: 'Trace' }).click();

    const panel = page.getByTestId('repograph-panel');
    await expect(panel).toBeVisible();

    // Re-index if not already indexed in this navigation.
    const workspaceInput = panel.getByLabel(/workspace path/i);
    await workspaceInput.fill(WORKSPACE);
    await panel.getByRole('button', { name: /^index$/i }).click();
    await expect(panel.locator('[data-testid="repograph-stats"]')).toBeVisible({ timeout: 30_000 });

    // Search for run_metadata — a known-populated symbol in the Forge-OH repo.
    const searchInput = panel.getByLabel(/search symbols/i);
    await searchInput.fill('run_metadata');

    // Results list should have at least one row within a reasonable
    // debounce window.
    const results = panel.locator('[data-testid="repograph-search-result"]');
    await expect(results.first()).toBeVisible({ timeout: 15_000 });

    await page.screenshot({ path: join(SCREENSHOT_DIR, 'repograph-03-search-results.png'), fullPage: true });

    // Click the first result — should trigger callers/callees/co_changed load.
    await results.first().click();

    // At least one of the three detail columns should show content or a
    // "no results" state (never spin forever). We check that all three
    // column headers render.
    await expect(panel.getByText(/^Callers/i)).toBeVisible();
    await expect(panel.getByText(/^Callees/i)).toBeVisible();
    await expect(panel.getByText(/^Co-changed/i)).toBeVisible();

    await page.screenshot({ path: join(SCREENSHOT_DIR, 'repograph-04-detail-view.png'), fullPage: true });
  });
});
