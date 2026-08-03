/**
 * run-detail.spec.ts
 *
 * Run detail against real BFF. Picks the first available run from the
 * runs list dynamically — no hard-coded IDs. If the BFF has zero runs
 * the test set is skipped (empty environment is a valid state).
 */
import { test, expect } from '@playwright/test';

async function firstRunId(page: import('@playwright/test').Page): Promise<string | null> {
  const res = await page.request.get(`${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  // BFF envelope: { data: [{ id, ... }, ...] } or bare array — accept both.
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{ id: string }>;
  return runs.length ? runs[0].id : null;
}

test.describe('Run Detail', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunId(page);
    await ctx.close();
  });

  test('detail page loads and shows tabs', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF — skipping detail test');
    await page.goto(`/runs/${runId!}`);
    // At least the Overview tab always renders once the detail loads.
    await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible();
  });

  test('all 7 tabs are present', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    for (const t of ['Overview', 'Files', 'Terminal', 'Browser', 'Metrics', 'Security', 'Trace']) {
      await expect(page.getByRole('tab', { name: t })).toBeVisible();
    }
  });

  test('files sub-route renders (feature-flag gated)', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}/files`);
    // Either changed files, empty state, or feature-flag banner.
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('artifacts sub-route renders', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}/artifacts`);
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('terminal sub-route renders', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}/terminal`);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
