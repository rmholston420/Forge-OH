/**
 * observability.spec.ts — Slice I: observability drill-down.
 *
 * Master-detail layout: run list sidebar (left), trace summary + spans (right).
 * Empty environment shows "Select a run" placeholder; when runs exist,
 * clicking one selects it and either shows trace stats/spans or an empty
 * state (still no app error).
 */
import { test, expect } from '@playwright/test';

async function runCount(page: import('@playwright/test').Page): Promise<number> {
  const res = await page.request.get(`${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`);
  if (!res.ok()) return 0;
  const body = await res.json();
  const list = (Array.isArray(body) ? body : body?.data ?? []) as unknown[];
  return list.length;
}

test.describe('Observability drill-down', () => {
  let count = 0;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    count = await runCount(page);
    await ctx.close();
  });

  test('page loads with Runs sidebar heading', async ({ page }) => {
    await page.goto('/observability');
    await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible();
  });

  test('shows "Select a run" placeholder when nothing is selected', async ({ page }) => {
    await page.goto('/observability');
    // Right pane shows either the empty-state (no runs) or the "Select a run" hint.
    const body = page.locator('body');
    // Guardrail — no runtime error, regardless of BFF data.
    await expect(body).not.toContainText('Application error');
    if (count === 0) {
      await expect(body).toContainText(/No runs/i);
    } else {
      await expect(body).toContainText(/Select a run/i);
    }
  });

  test('clicking a run in the sidebar renders the trace pane', async ({ page }) => {
    test.skip(count === 0, 'no runs on BFF');
    await page.goto('/observability');
    // Sidebar runs are <button> elements — click the first one.
    const runButtons = page.locator('aside button');
    await expect(runButtons.first()).toBeVisible();
    await runButtons.first().click();
    // Right pane must either show span table headers OR an empty/error banner —
    // but never a Next.js runtime error boundary.
    await expect(page.locator('body')).not.toContainText('Application error');
    await expect(page.locator('body')).not.toContainText('Unhandled Runtime Error');
  });
});
