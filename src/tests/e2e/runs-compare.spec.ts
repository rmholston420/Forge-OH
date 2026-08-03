/**
 * runs-compare.spec.ts — Slice G: /runs/compare wired to a toolbar button on
 * the runs list. Modal appears when ≥2 runs exist. Assertion strategy:
 *
 *   - <2 runs:  Compare button is present but disabled.
 *   - ≥2 runs:  clicking Compare opens the modal with the two run selects.
 */
import { test, expect } from '@playwright/test';

async function runCount(page: import('@playwright/test').Page): Promise<number> {
  const res = await page.request.get(`${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`);
  if (!res.ok()) return 0;
  const body = await res.json();
  const list = (Array.isArray(body) ? body : body?.data ?? []) as unknown[];
  return list.length;
}

test.describe('Runs Compare modal', () => {
  let count = 0;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    count = await runCount(page);
    await ctx.close();
  });

  test('Compare button renders on runs list toolbar', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: 'Compare' })).toBeVisible();
  });

  test('Compare button is disabled when <2 runs exist', async ({ page }) => {
    test.skip(count >= 2, 'only relevant when <2 runs');
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: 'Compare' })).toBeDisabled();
  });

  test('Compare opens modal with Base + Fork selects when ≥2 runs', async ({ page }) => {
    test.skip(count < 2, 'needs ≥2 runs on BFF');
    await page.goto('/runs');
    await page.getByRole('button', { name: 'Compare' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(/Compare runs/i);
    await expect(dialog).toContainText(/Base run/i);
    await expect(dialog).toContainText(/Fork run/i);
  });
});
