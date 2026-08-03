/**
 * run-plan.spec.ts — Slice C: /runs/{id}/plan wired into the Plan tab.
 *
 * Picks the first available run from BFF. If none, tests skip
 * (empty environment is valid).
 */
import { test, expect } from '@playwright/test';

async function firstRunId(page: import('@playwright/test').Page): Promise<string | null> {
  const res = await page.request.get(`${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{ id: string }>;
  return runs.length ? runs[0].id : null;
}

test.describe('Run Plan tab', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunId(page);
    await ctx.close();
  });

  test('Plan tab is present in run detail', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    await expect(page.getByRole('tab', { name: 'Plan' })).toBeVisible();
  });

  test('clicking Plan tab renders without app error', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    await page.getByRole('tab', { name: 'Plan' }).click();
    // Accepts any of: rendered steps, empty state, or loading skeleton.
    // Guardrail: no Next.js runtime error boundary.
    await expect(page.locator('body')).not.toContainText('Application error');
    await expect(page.locator('body')).not.toContainText('Unhandled Runtime Error');
  });

  test('Plan API endpoint returns a 2xx/4xx envelope (not 5xx)', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    const url = `${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs/${runId}/plan`;
    const res = await page.request.get(url);
    expect(res.status()).toBeLessThan(500);
  });
});
