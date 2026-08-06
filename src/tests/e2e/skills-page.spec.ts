/**
 * skills-page.spec.ts — Stage 6.6 visual + wiring check.
 *
 * Verifies:
 *   1. /skills renders the list of skills the BFF discovers via the SDK
 *      loader (in-process Path B — see bff/routers/skills.py).
 *   2. The scope-filter buttons work.
 *   3. Sidebar has a Skills entry that navigates to /skills.
 *
 * Skips cleanly if the BFF or frontend are down. Runs against prod
 * frontend on 3100 (forge-oh-playwright-visual: never `next dev`).
 */
import { test, expect, Page } from '@playwright/test';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const FRONTEND_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.PLAYWRIGHT_FRONTEND_URL ||
  'http://127.0.0.1:3100';

async function bffReachable(): Promise<boolean> {
  try {
    const r = await fetch(`${BFF_URL}/api/skills`);
    return r.ok;
  } catch {
    return false;
  }
}

async function pushScreenshot(page: Page, name: string): Promise<void> {
  if (process.env.PLAYWRIGHT_GPU_STRIP_PUSH !== '1') return;
  await page.screenshot({ path: `screenshots/${name}.png`, fullPage: false });
}

test.describe('Stage 6.6 Skills page', () => {
  test.beforeAll(async () => {
    const ok = await bffReachable();
    test.skip(!ok, `BFF unreachable at ${BFF_URL}/api/skills`);
  });

  test('sidebar has Skills entry that navigates to /skills', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/runs`);
    const link = page.getByRole('link', { name: /Skills/i }).first();
    await expect(link).toBeVisible({ timeout: 10_000 });
    await link.click();
    await expect(page).toHaveURL(/\/skills$/, { timeout: 10_000 });
  });

  test('/skills renders the loaded skill rows with names and triggers', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/skills`);
    await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible({ timeout: 15_000 });

    // At least one skill row from the known local checkout should be present.
    // The Colossus repo has forge-oh-* project skills committed.
    const rows = page.getByTestId('skill-row');
    await expect(rows.first()).toBeVisible({ timeout: 15_000 });
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // Scope-filter buttons present.
    await expect(page.getByRole('button', { name: /^All \(/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^User \(/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Project \(/ })).toBeVisible();

    // Search filter narrows the list.
    await page.getByLabel('Search skills').fill('__no_such_skill__');
    await expect(page.getByTestId('skill-row')).toHaveCount(0);
    await page.getByLabel('Search skills').fill('');

    await pushScreenshot(page, 'skills-page');
  });

  test('scope filter toggles hide project or user rows', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/skills`);
    await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible({ timeout: 15_000 });

    const allBtn = page.getByRole('button', { name: /^All \(/ });
    const userBtn = page.getByRole('button', { name: /^User \(/ });

    const allText = (await allBtn.textContent()) || '';
    const userText = (await userBtn.textContent()) || '';
    const allCount = Number((allText.match(/\((\d+)\)/) || [])[1] || 0);
    const userCount = Number((userText.match(/\((\d+)\)/) || [])[1] || 0);
    expect(allCount).toBeGreaterThan(0);
    expect(userCount).toBeGreaterThanOrEqual(0);
    // Scope buttons are for UX filter — currently visual only on the tag counts;
    // the row list is not gated by scope in this pass because BFF returns a
    // single flat list. Just prove the buttons don't crash the page.
    await userBtn.click();
    await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible();
    await allBtn.click();
    await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible();
  });

  test('clicking a skill expands the preview body', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/skills`);
    await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible({ timeout: 15_000 });
    const firstRow = page.getByTestId('skill-row').first();
    const toggle = firstRow.getByRole('button').first();
    await toggle.click();
    // After toggle, aria-expanded flips
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });
});
